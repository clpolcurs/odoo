"""MCP server exposing the learning_japanese REST API to Claude."""

import functools
import inspect
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated, Any, Literal, TypeVar

import anyio
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from . import prompts
from .audio import AudioFile, download_audio, header_filename, read_audio_file
from .client import LJClient
from .config import ConfigError, Settings

Json = dict[str, Any]
ToolFn = TypeVar("ToolFn", bound=Callable[..., Any])

BOOK_ITEMS_CAP = 100  # ~45 KB of summaries, well under Claude Code's default 25,000-token limit for a tool result
CLEARABLE = {"level", "verb_group", "honorific_type"}  # enum fields where the value "none" sends null
HTML_FIELDS = ("html_hover", "html_ruby")  # generated from the markup and several times larger than it

READ_ONLY = ToolAnnotations(readOnlyHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

INSTRUCTIONS = """\
Content of the Odoo addon learning_japanese: Japanese course material (JLPT N5 to N1) explained in Vietnamese.
- Comprehensive items are reading, listening, grammar and example items, told apart by tags (Reading, Listening, \
Grammar, Example, Writing, Speaking). Grammar points are the items tagged Grammar.
- Books contain lessons; comprehensive items and vocabulary entries are linked to lessons.
- Markup is HTML where every word written with kanji is <<漢字 - よみ>> with its hiragana reading, and the Vietnamese \
translation of each paragraph follows it in {{...}}. Check markup with lj_preview_markup before saving it.
- Every record has a version. Writes take the version you last read (sent as If-Match); on HTTP 412 re-read the \
record, re-apply the change and retry with the new version.
- Lists are paginated: pass next_cursor as cursor until it is null.
- Tag names, lesson ids, topic (context tag) ids and part-of-speech ids come from lj_list_catalog.
- Items come without html_hover and html_ruby, the HTML generated from the markup, unless a tool is asked for it \
with include_html.
"""

MARKUP_HELP = (
    "House markup: HTML paragraphs where every word written with kanji is <<漢字 - よみ>> with a hiragana reading "
    "(okurigana outside: <<悪 - わる>>い) and the Vietnamese translation of each paragraph follows it in {{...}}, "
    "e.g. <p><<女 - おんな>>の<<人 - ひと>>が<<来 - き>>ました。<br/>{{Người phụ nữ đã đến.}}</p>. "
    "Check it with lj_preview_markup first."
)

# Shared parameter types; their descriptions are what Claude reads.
ComprehensiveId = Annotated[int, Field(ge=1, description="Id of the comprehensive item.")]
VocabularyId = Annotated[int, Field(ge=1, description="Id of the vocabulary entry.")]
Version = Annotated[
    str,
    Field(
        min_length=1,
        description="`version` of the record from your last read or write, sent as If-Match. "
        "A stale version fails with HTTP 412.",
    ),
]
OptionalVersion = Annotated[
    str | None,
    Field(
        min_length=1,
        description="Optional `version` of the item; if given, the write fails with HTTP 412 "
        "when the item changed since.",
    ),
]
Limit = Annotated[int, Field(ge=1, le=200, description="Page size, 1-200.")]
Cursor = Annotated[str | None, Field(description="`next_cursor` of the previous page; omit for the first page.")]
LevelFilter = Annotated[
    str | None,
    Field(description="JLPT level(s) N5, N4, N3, N2, N1, comma separated (e.g. 'N3,N2'); 'none' = without a level."),
]
TagFilter = Annotated[
    str | None,
    Field(
        description="Tag name(s), comma separated; an item matches if it has any of them. "
        "Tags: Reading, Listening, Grammar, Example, Writing, Speaking (lj_list_catalog lists them)."
    ),
]
BookFilter = Annotated[int | None, Field(ge=1, description="Only records linked to a lesson of this book.")]
LessonFilter = Annotated[int | None, Field(ge=1, description="Only records linked to this lesson.")]
Published = Annotated[
    bool | None,
    Field(description="true: only records of a book published to NihonGo; false: only the others."),
]

IncludeHtml = Annotated[
    bool,
    Field(description="Also return html_hover and html_ruby, the HTML generated from the markup (large)."),
]

Level = Literal["N5", "N4", "N3", "N2", "N1"]
LevelChange = Literal["N5", "N4", "N3", "N2", "N1", "none"]
LinkAction = Annotated[Literal["add", "remove"], Field(description="add links the lesson, remove unlinks it.")]

_TITLE = Field(
    min_length=1,
    max_length=1000,
    description="Title, e.g. '[Cơ bản] そうですね'. Keep usage prefixes such as PI or thể ta; "
    "a leading [...] is a filter label that title_display leaves out.",
)
Title = Annotated[str, _TITLE]
OptionalTitle = Annotated[str | None, _TITLE]
Tags = Annotated[
    list[str] | None,
    Field(
        description="Existing tag names, e.g. ['Reading'], ['Listening'], ['Grammar'], ['Example']; replaces all tags."
    ),
]
LessonIds = Annotated[
    list[int] | None, Field(description="Lesson ids (lj_get_book, lj_list_catalog); replaces all lessons.")
]
Markup = Annotated[str | None, Field(max_length=200_000, description=MARKUP_HELP)]
Description = Annotated[str | None, Field(description="Description or explanation of the item, in Vietnamese.")]
GrammarPatterns = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=100)]] | None,
    Field(max_length=30, description="Dictionary-form match patterns of a grammar point, e.g. ['とする']; at most 30."),
]

_TERM = Field(min_length=1, max_length=200, description="The word as taught, e.g. 理解します or 元々.")
Term = Annotated[str, _TERM]
OptionalTerm = Annotated[str | None, _TERM]
Hiragana = Annotated[str | None, Field(description="Reading in hiragana, e.g. りかいします.")]
Katakana = Annotated[str | None, Field(description="Spelling in katakana (loanwords).")]
Romaji = Annotated[str | None, Field(description="Reading in romaji.")]
MeaningVi = Annotated[str | None, Field(description="Vietnamese meaning.")]
HanViet = Annotated[str | None, Field(description="Sino-Vietnamese reading, e.g. LÝ GIẢI.")]
VocabularyLevel = Annotated[LevelChange | None, Field(description="JLPT level N5 (easiest) to N1; 'none' removes it.")]
IsIntransitive = Annotated[bool | None, Field(description="true for an intransitive verb (自動詞).")]
VerbGroup = Annotated[
    Literal["group1", "group2", "group3", "none"] | None,
    Field(description="Verb group; 'none' removes it."),
]
HonorificType = Annotated[
    Literal["sonkeigo", "kenjougo", "none"] | None,
    Field(description="Honorific type; 'none' removes it."),
]
PartOfSpeechIds = Annotated[
    list[int] | None, Field(description="Part-of-speech ids (lj_list_catalog); replaces the list.")
]
ContextTagIds = Annotated[
    list[int] | None, Field(description="Topic (context tag) ids (lj_list_catalog); replaces the list.")
]
ExamplesMarkup = Annotated[
    str | None,
    Field(
        max_length=100_000,
        description="Example sentences in the house markup "
        "(<<漢字 - よみ>> readings, {{...}} Vietnamese translations).",
    ),
]


class VerbForms(BaseModel):
    """Conjugated forms of a verb; only the forms given are sent."""

    model_config = ConfigDict(extra="forbid")

    dictionary: str | None = None
    past: str | None = None
    negative: str | None = None
    te: str | None = None
    potential: str | None = None
    passive: str | None = None
    causative: str | None = None
    causative_passive: str | None = None
    conditional: str | None = None
    imperative: str | None = None
    volitional: str | None = None
    prohibitive: str | None = None


Forms = Annotated[VerbForms | None, Field(description="Conjugated forms of a verb; only the forms given are sent.")]


class VocabularyEntry(BaseModel):
    """One entry: with `id` it updates that vocabulary, without `id` it creates one (term required)."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[int | None, Field(ge=1, description="Vocabulary to update; omit to create.")] = None
    version: Annotated[str | None, Field(min_length=1, description="Optional lock, checked like If-Match.")] = None
    term: OptionalTerm = None
    hiragana: Hiragana = None
    katakana: Katakana = None
    romaji: Romaji = None
    meaning_vi: MeaningVi = None
    han_viet: HanViet = None
    level: VocabularyLevel = None
    is_intransitive: IsIntransitive = None
    verb_group: VerbGroup = None
    honorific_type: HonorificType = None
    forms: Forms = None
    part_of_speech_ids: PartOfSpeechIds = None
    context_tag_ids: ContextTagIds = None
    lesson_ids: LessonIds = None
    examples_markup: ExamplesMarkup = None


class GrammarOverride(BaseModel):
    """A grammar point pinned to, or hidden from, a reading or listening item."""

    model_config = ConfigDict(extra="forbid")

    grammar_id: Annotated[int, Field(ge=1, description="Id of a comprehensive item tagged Grammar.")]
    action: Annotated[
        Literal["pin", "hide"],
        Field(
            description="pin attaches the grammar point to the item; hide keeps it off the item even when "
            "its grammar_patterns match the text."
        ),
    ]
    note: Annotated[str | None, Field(max_length=500, description="Optional note.")] = None


def _json_value(key: str, value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_unset=True)
    return None if key in CLEARABLE and value == "none" else value


def _body(**fields: Any) -> Json:
    """The fields the caller gave (None means not given); 'none' clears level, verb_group or honorific_type."""
    return {key: _json_value(key, value) for key, value in fields.items() if value is not None}


def _without_html(data: Json) -> Json:
    """`data` without the HTML generated from its markup."""
    return {key: value for key, value in data.items() if key not in HTML_FIELDS}


def _tool(mcp: FastMCP, annotations: ToolAnnotations) -> Callable[[ToolFn], ToolFn]:
    """Register a function returning API JSON as a tool; its docstring is the description Claude reads."""

    def register(fn: ToolFn) -> ToolFn:
        @functools.wraps(fn)  # FastMCP reads the parameters of `fn` through __wrapped__
        async def compact_json(*args: Any, **kwargs: Any) -> TextContent:
            result = await fn(*args, **kwargs)
            return TextContent(type="text", text=json.dumps(result, ensure_ascii=False, separators=(",", ":")))

        mcp.add_tool(
            compact_json,
            description=inspect.cleandoc(fn.__doc__ or ""),
            annotations=annotations,
            structured_output=False,
        )
        return fn

    return register


def build_server(settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> FastMCP:
    """Create the server; `transport` replaces the network (API and audio downloads) in tests."""
    api = LJClient(settings, transport=transport)

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[None]:
        try:
            yield
        finally:
            with anyio.CancelScope(shield=True):
                await api.aclose()

    mcp = FastMCP("learning-japanese", instructions=INSTRUCTIONS, lifespan=lifespan)
    _add_read_tools(mcp, api)
    _add_write_tools(mcp, api, partial(download_audio, timeout=settings.timeout, transport=transport))
    if settings.allow_delete:
        _add_delete_tools(mcp, api)
    mcp.prompt()(prompts.annotate_japanese_text)
    mcp.prompt()(prompts.review_readings)
    return mcp


def _add_read_tools(mcp: FastMCP, api: LJClient) -> None:
    tool = partial(_tool, mcp)

    @tool(READ_ONLY)
    async def lj_search_comprehensives(
        q: Annotated[str | None, Field(description="Case-insensitive text searched in title and description.")] = None,
        level: LevelFilter = None,
        tag: TagFilter = None,
        book_id: BookFilter = None,
        lesson_id: LessonFilter = None,
        published: Published = None,
        limit: Limit = 50,
        cursor: Cursor = None,
    ) -> Json:
        """Search comprehensive items: reading, listening, grammar, example... items, told apart by their tags.

        Returns {"items": [...], "next_cursor": ...}. Items are summaries (id, title, title_display, level, tags,
        lesson_ids, book_ids, published, has_markup, audio, updated_at, version) without markup or HTML;
        lj_get_comprehensive returns one item in full. Pass next_cursor as cursor for the next page.
        """
        return await api.get(
            "/comprehensives",
            {
                "view": "summary",
                "q": q,
                "level": level,
                "tag": tag,
                "book_id": book_id,
                "lesson_id": lesson_id,
                "published": published,
                "limit": limit,
                "cursor": cursor,
            },
        )

    @tool(READ_ONLY)
    async def lj_get_comprehensive(comprehensive_id: ComprehensiveId, include_html: IncludeHtml = False) -> Json:
        """Get one comprehensive item in full.

        Includes markup (the source in the house markup), is_finalized, description, grammar_patterns,
        grammar_overrides, audio and `version`; html_hover and html_ruby (the HTML generated from the markup)
        only with include_html.
        Keep `version`: every write to this item needs it (lj_update_comprehensive, lj_set_grammar_patterns...),
        and it changes with each write; the write tools return the new one.
        """
        item = await api.get(f"/comprehensives/{comprehensive_id}")
        return item if include_html else _without_html(item)

    @tool(READ_ONLY)
    async def lj_list_books(
        q: Annotated[str | None, Field(description="Case-insensitive text searched in the book name.")] = None,
        published: Annotated[
            bool | None, Field(description="true: only books published to NihonGo; false: only the others.")
        ] = None,
        limit: Limit = 50,
        cursor: Cursor = None,
    ) -> Json:
        """List textbooks with their lessons (id, name, item_count, vocabulary_count).

        Returns {"items": [...], "next_cursor": ...}; pass next_cursor as cursor for the next page.
        """
        return await api.get("/books", {"q": q, "published": published, "limit": limit, "cursor": cursor})

    @tool(READ_ONLY)
    async def lj_get_book(book_id: Annotated[int, Field(ge=1, description="Id of the book.")]) -> Json:
        """Get a textbook with its lessons and the summaries of all its comprehensive items, in one call.

        Returns {"book": {..., "lessons": [{id, name, item_count, vocabulary_count}]}, "items": [...],
        "next_cursor": ...}. Items are the summaries of lj_search_comprehensives; their lesson_ids tell which
        lessons they belong to. At most 100 items are returned: when next_cursor is not null, continue with
        lj_search_comprehensives(book_id=..., cursor=next_cursor).
        """
        book = await api.get(f"/books/{book_id}")
        items, next_cursor = await api.collect(
            "/comprehensives", {"book_id": book_id, "view": "summary"}, cap=BOOK_ITEMS_CAP
        )
        return {"book": book, "items": items, "next_cursor": next_cursor}

    @tool(READ_ONLY)
    async def lj_search_grammar(
        q: Annotated[str | None, Field(description="Text searched in title and description, e.g. 'とする'.")] = None,
        level: LevelFilter = None,
        limit: Limit = 50,
        cursor: Cursor = None,
    ) -> Json:
        """Search grammar points, i.e. the comprehensive items tagged Grammar.

        Returns {"items": [...], "next_cursor": ...} with the summaries of lj_search_comprehensives;
        lj_get_comprehensive gives the explanation (markup, description) and grammar_patterns of one point.
        """
        return await api.get(
            "/comprehensives",
            {"grammar": True, "q": q, "level": level, "limit": limit, "cursor": cursor, "view": "summary"},
        )

    @tool(READ_ONLY)
    async def lj_list_catalog(
        catalog: Annotated[
            Literal["tags", "lessons", "context_tags", "parts_of_speech", "hanviet"],
            Field(
                description="tags: tags of comprehensive items (names for `tags`); lessons: lessons with their "
                "book_id (`lesson_ids`); context_tags: vocabulary topics (`context_tag_ids`); parts_of_speech: "
                "`part_of_speech_ids`; hanviet: Sino-Vietnamese readings of single kanji."
            ),
        ],
        book_id: Annotated[int | None, Field(ge=1, description="lessons only: the lessons of this book.")] = None,
        kanji: Annotated[
            str | None, Field(description="hanviet only: the kanji to look up, e.g. '理解' gives 理 and 解.")
        ] = None,
        limit: Limit = 200,
        cursor: Cursor = None,
    ) -> Json:
        """List the names and ids that the other tools take: tags, lessons, topics, parts of speech, Hán Việt.

        Returns {"items": [...], "next_cursor": ...}; pass next_cursor as cursor for the next page.
        """
        if book_id is not None and catalog != "lessons":
            raise ValueError("book_id only applies to catalog='lessons'")
        if kanji is not None and catalog != "hanviet":
            raise ValueError("kanji only applies to catalog='hanviet'")
        return await api.get(
            "/" + catalog.replace("_", "-"), {"book_id": book_id, "kanji": kanji, "limit": limit, "cursor": cursor}
        )

    @tool(READ_ONLY)
    async def lj_search_vocabulary(
        q: Annotated[
            str | None, Field(description="Case-insensitive text searched in the term, its kana and its meaning.")
        ] = None,
        level: LevelFilter = None,
        book_id: BookFilter = None,
        lesson_id: LessonFilter = None,
        context_tag_id: Annotated[int | None, Field(ge=1, description="Only words of this topic.")] = None,
        published: Published = None,
        limit: Limit = 50,
        cursor: Cursor = None,
    ) -> Json:
        """Search vocabulary entries.

        Returns {"items": [...], "next_cursor": ...}; each item is a full entry (term, hiragana, katakana, romaji,
        meaning_vi, han_viet, level, verb data and forms, part_of_speech_ids, context_tag_ids, lesson_ids,
        examples_markup, version...). Pass next_cursor as cursor for the next page.
        """
        return await api.get(
            "/vocabularies",
            {
                "q": q,
                "level": level,
                "book_id": book_id,
                "lesson_id": lesson_id,
                "context_tag_id": context_tag_id,
                "published": published,
                "limit": limit,
                "cursor": cursor,
            },
        )

    @tool(READ_ONLY)
    async def lj_get_vocabulary(vocabulary_id: VocabularyId) -> Json:
        """Get one vocabulary entry, including the `version` that lj_update_vocabulary needs."""
        return await api.get(f"/vocabularies/{vocabulary_id}")

    @tool(READ_ONLY)
    async def lj_preview_markup(
        markup: Annotated[str, Field(max_length=200_000, description="The markup to check.")],
        include_html: IncludeHtml = False,
    ) -> Json:
        """Convert markup exactly as Odoo does when saving it and report problems; nothing is stored.

        Markup is HTML where <<漢字 - よみ>> gives the hiragana reading of a kanji word (<<漢字>> lets the server
        guess it) and {{...}} holds the Vietnamese translation of the paragraph.
        Returns stats (blocks, markers, explicit_readings, auto_readings, translations) and issues with a code:
        unbalanced_marker, empty_marker, auto_reading (`reading` is the server's guess, often wrong),
        kanji_without_reading (kanji outside a marker), reading_not_kana, unbalanced_translation,
        missing_translation (a paragraph without {{...}} while others have one); `block` is the 0-based paragraph.
        Fix every issue before saving.
        With include_html, also the html_hover and html_ruby that saving would store.
        """
        preview = await api.request("POST", "/markup/preview", json={"markup": markup})
        return preview if include_html else _without_html(preview)

    @tool(READ_ONLY)
    async def lj_list_issues(
        code: Annotated[
            str | None,
            Field(
                description="Issue code(s), comma separated: missing_level, missing_markup, not_finalized, "
                "unbalanced_markup, kanji_without_reading, auto_readings, missing_audio, "
                "grammar_missing_patterns, not_published. Default: all codes except not_published."
            ),
        ] = None,
        level: LevelFilter = None,
        tag: Annotated[
            str | None, Field(description="Tag name(s), comma separated; default Reading,Listening,Grammar.")
        ] = None,
        book_id: BookFilter = None,
        published: Published = None,
        limit: Limit = 50,
        cursor: Cursor = None,
    ) -> Json:
        """List the comprehensive items that need fixing before they go to NihonGo (QA report).

        Only items with at least one issue are listed. Returns {"items": [{id, title, level, tags, book_ids,
        published, issues: [{code, count, details}]}], "summary": {code: count over the whole filtered set},
        "next_cursor": ...}; pass next_cursor as cursor for the next page.
        """
        return await api.get(
            "/qa/issues",
            {
                "code": code,
                "level": level,
                "tag": tag,
                "book_id": book_id,
                "published": published,
                "limit": limit,
                "cursor": cursor,
            },
        )


def _add_write_tools(mcp: FastMCP, api: LJClient, download: Callable[[str], Awaitable[AudioFile]]) -> None:
    tool = partial(_tool, mcp)

    @tool(WRITE)
    async def lj_create_comprehensive(
        title: Title,
        level: Annotated[Level | None, Field(description="JLPT level, N5 (easiest) to N1.")] = None,
        tags: Tags = None,
        lesson_ids: LessonIds = None,
        markup: Markup = None,
        description: Description = None,
        grammar_patterns: GrammarPatterns = None,
    ) -> Json:
        """Create a comprehensive item and return it with its `version`.

        Tags decide the kind of item (e.g. ['Reading'], ['Listening'], ['Grammar']). The markup is converted to
        html_hover and html_ruby exactly as when it is typed in Odoo. Add audio afterwards with
        lj_set_audio_from_url or lj_set_audio_from_file.
        """
        body = _body(
            title=title,
            level=level,
            tags=tags,
            lesson_ids=lesson_ids,
            markup=markup,
            description=description,
            grammar_patterns=grammar_patterns,
        )
        return _without_html(await api.request("POST", "/comprehensives", json=body))

    @tool(WRITE)
    async def lj_update_comprehensive(
        comprehensive_id: ComprehensiveId,
        version: Version,
        title: OptionalTitle = None,
        level: Annotated[LevelChange | None, Field(description="JLPT level N5-N1; 'none' removes the level.")] = None,
        tags: Tags = None,
        lesson_ids: LessonIds = None,
        markup: Markup = None,
        description: Description = None,
        grammar_patterns: GrammarPatterns = None,
    ) -> Json:
        """Change fields of a comprehensive item; parameters left out stay unchanged.

        `version` comes from lj_get_comprehensive (or the previous write). If the item changed meanwhile the call
        fails with HTTP 412 and current_version: re-read the item, re-apply the change and retry.
        tags and lesson_ids replace the whole list; an empty string clears markup or description; a new markup is
        converted again (html_hover, html_ruby). Returns the updated item with its new version.
        """
        body = _body(
            title=title,
            level=level,
            tags=tags,
            lesson_ids=lesson_ids,
            markup=markup,
            description=description,
            grammar_patterns=grammar_patterns,
        )
        if not body:
            raise ValueError("nothing to update: give at least one field to change")
        item = await api.request("PATCH", f"/comprehensives/{comprehensive_id}", json=body, version=version)
        return _without_html(item)

    @tool(WRITE)
    async def lj_set_audio_from_url(
        comprehensive_id: ComprehensiveId,
        url: Annotated[str, Field(description="Direct http(s) link to the audio file, not to an HTML page.")],
        version: OptionalVersion = None,
        filename: Annotated[
            str | None, Field(description="File name to keep, e.g. n2-dd-1ban.mp3; default: the downloaded name.")
        ] = None,
    ) -> Json:
        """Download an audio file from a URL and make it the audio of a comprehensive item, replacing any audio.

        lj-mcp downloads the file itself, following redirects (the Odoo server never fetches URLs). It must be at
        most 30 MiB and be audio: an audio/* Content-Type, or an audio extension (.mp3, .m4a, .aac, .wav, .ogg,
        .oga, .opus, .flac, .weba) unless the server answers with a text or HTML page.
        Returns the updated item (audio, new version).
        """
        api.settings.require_api_key()  # fail before downloading
        audio = await download(url)
        return await _put_audio(api, comprehensive_id, audio, filename, version)

    @tool(WRITE)
    async def lj_set_audio_from_file(
        comprehensive_id: ComprehensiveId,
        path: Annotated[str, Field(description="Absolute path of a local audio file (~ is expanded).")],
        version: OptionalVersion = None,
        filename: Annotated[str | None, Field(description="File name to keep; default: the file's name.")] = None,
    ) -> Json:
        """Upload a local audio file as the audio of a comprehensive item, replacing any audio.

        The path must be absolute; the file must be at most 30 MiB with an audio extension (.mp3, .m4a, .aac,
        .wav, .ogg, .oga, .opus, .flac, .weba). Returns the updated item (audio, new version).
        """
        audio = await anyio.to_thread.run_sync(read_audio_file, path)
        return await _put_audio(api, comprehensive_id, audio, filename, version)

    @tool(WRITE)
    async def lj_create_vocabulary(
        term: Term,
        hiragana: Hiragana = None,
        katakana: Katakana = None,
        romaji: Romaji = None,
        meaning_vi: MeaningVi = None,
        han_viet: HanViet = None,
        level: VocabularyLevel = None,
        is_intransitive: IsIntransitive = None,
        verb_group: VerbGroup = None,
        honorific_type: HonorificType = None,
        forms: Forms = None,
        part_of_speech_ids: PartOfSpeechIds = None,
        context_tag_ids: ContextTagIds = None,
        lesson_ids: LessonIds = None,
        examples_markup: ExamplesMarkup = None,
    ) -> Json:
        """Create a vocabulary entry and return it with its `version`.

        A term may exist several times, but term and meaning_vi together must be unique (HTTP 409 otherwise).
        """
        body = _body(
            term=term,
            hiragana=hiragana,
            katakana=katakana,
            romaji=romaji,
            meaning_vi=meaning_vi,
            han_viet=han_viet,
            level=level,
            is_intransitive=is_intransitive,
            verb_group=verb_group,
            honorific_type=honorific_type,
            forms=forms,
            part_of_speech_ids=part_of_speech_ids,
            context_tag_ids=context_tag_ids,
            lesson_ids=lesson_ids,
            examples_markup=examples_markup,
        )
        return await api.request("POST", "/vocabularies", json=body)

    @tool(WRITE)
    async def lj_update_vocabulary(
        vocabulary_id: VocabularyId,
        version: Version,
        term: OptionalTerm = None,
        hiragana: Hiragana = None,
        katakana: Katakana = None,
        romaji: Romaji = None,
        meaning_vi: MeaningVi = None,
        han_viet: HanViet = None,
        level: VocabularyLevel = None,
        is_intransitive: IsIntransitive = None,
        verb_group: VerbGroup = None,
        honorific_type: HonorificType = None,
        forms: Forms = None,
        part_of_speech_ids: PartOfSpeechIds = None,
        context_tag_ids: ContextTagIds = None,
        lesson_ids: LessonIds = None,
        examples_markup: ExamplesMarkup = None,
    ) -> Json:
        """Change fields of a vocabulary entry; parameters left out stay unchanged.

        `version` comes from lj_get_vocabulary or lj_search_vocabulary; on HTTP 412 re-read the entry and retry.
        Id lists replace the whole list; an empty string clears a text field. Returns the updated entry.
        """
        body = _body(
            term=term,
            hiragana=hiragana,
            katakana=katakana,
            romaji=romaji,
            meaning_vi=meaning_vi,
            han_viet=han_viet,
            level=level,
            is_intransitive=is_intransitive,
            verb_group=verb_group,
            honorific_type=honorific_type,
            forms=forms,
            part_of_speech_ids=part_of_speech_ids,
            context_tag_ids=context_tag_ids,
            lesson_ids=lesson_ids,
            examples_markup=examples_markup,
        )
        if not body:
            raise ValueError("nothing to update: give at least one field to change")
        return await api.request("PATCH", f"/vocabularies/{vocabulary_id}", json=body, version=version)

    @tool(WRITE)
    async def lj_bulk_update_vocabulary(
        items: Annotated[
            list[VocabularyEntry],
            Field(min_length=1, max_length=100, description="1 to 100 entries, saved in this order."),
        ],
    ) -> Json:
        """Create and update up to 100 vocabulary entries in one transaction: all are saved or none is.

        An entry with `id` updates that vocabulary: only the fields it contains change, null or 'none' clears one,
        and its optional `version` is checked like If-Match. An entry without `id` creates a vocabulary.
        Returns {"items": [...]} in request order. On failure nothing is saved and each problem carries the
        0-based `index` of its entry.
        """
        entries = [
            {key: _json_value(key, value) for key, value in entry.model_dump(exclude_unset=True).items()}
            for entry in items
        ]
        return await api.request("POST", "/vocabularies/bulk", json={"items": entries})

    @tool(WRITE)
    async def lj_link_lesson(
        comprehensive_id: ComprehensiveId,
        lesson_id: Annotated[
            int, Field(ge=1, description="The lesson (lj_get_book and lj_list_catalog list lesson ids).")
        ],
        action: LinkAction = "add",
        version: OptionalVersion = None,
    ) -> Json:
        """Link a comprehensive item to one more lesson, or unlink it from one, keeping its other lessons.

        Reads the item, changes lesson_ids and saves them with If-Match of the version just read, or of `version`
        when given (a stale one fails with HTTP 412). Nothing is written when the lesson is already linked (add)
        or not linked (remove). Returns the item.
        """
        item = await api.get(f"/comprehensives/{comprehensive_id}")
        lesson_ids: list[int] = item["lesson_ids"]
        if action == "add":
            new_ids = lesson_ids if lesson_id in lesson_ids else [*lesson_ids, lesson_id]
        else:
            new_ids = [existing for existing in lesson_ids if existing != lesson_id]
        if new_ids != lesson_ids:
            item = await api.request(
                "PATCH",
                f"/comprehensives/{comprehensive_id}",
                json={"lesson_ids": new_ids},
                version=version or item["version"],
            )
        return _without_html(item)

    @tool(WRITE)
    async def lj_set_grammar_patterns(
        comprehensive_id: ComprehensiveId,
        version: Version,
        patterns: Annotated[
            list[Annotated[str, Field(min_length=1, max_length=100)]],
            Field(max_length=30, description="Dictionary-form patterns, e.g. ['とする']; [] removes them all."),
        ],
    ) -> Json:
        """Replace the match patterns of a grammar point (an item tagged Grammar).

        The patterns are dictionary forms used to find the grammar point in reading and listening texts, e.g.
        とする; at most 30 of at most 100 characters. Returns the updated item with its new version.
        """
        item = await api.request(
            "PATCH", f"/comprehensives/{comprehensive_id}", json={"grammar_patterns": patterns}, version=version
        )
        return _without_html(item)

    @tool(WRITE)
    async def lj_set_grammar_overrides(
        comprehensive_id: ComprehensiveId,
        overrides: Annotated[
            list[GrammarOverride], Field(max_length=200, description="The complete new list; [] clears it.")
        ],
        version: OptionalVersion = None,
    ) -> Json:
        """Replace the grammar overrides of a reading or listening item: grammar points pinned to or hidden from it.

        The list replaces the current one (grammar_overrides in lj_get_comprehensive), so repeat the overrides to
        keep. Returns {"items": [...], "version": <new version of the item>}.
        """
        body = {"items": [override.model_dump() for override in overrides]}
        return await api.request(
            "PUT", f"/comprehensives/{comprehensive_id}/grammar-overrides", json=body, version=version
        )


def _add_delete_tools(mcp: FastMCP, api: LJClient) -> None:
    tool = partial(_tool, mcp)

    @tool(DESTRUCTIVE)
    async def lj_delete_comprehensive(comprehensive_id: ComprehensiveId, version: Version) -> Json:
        """Delete a comprehensive item for good; this cannot be undone. Only use it when the user asked for it.

        `version` must be the item's current version (If-Match); HTTP 412 if the item changed since.
        """
        await api.request("DELETE", f"/comprehensives/{comprehensive_id}", version=version)
        return {"id": comprehensive_id, "deleted": True}

    @tool(DESTRUCTIVE)
    async def lj_delete_vocabulary(vocabulary_id: VocabularyId, version: Version) -> Json:
        """Delete a vocabulary entry for good; this cannot be undone. Only use it when the user asked for it.

        `version` must be the entry's current version (If-Match); HTTP 412 if the entry changed since.
        """
        await api.request("DELETE", f"/vocabularies/{vocabulary_id}", version=version)
        return {"id": vocabulary_id, "deleted": True}


async def _put_audio(
    api: LJClient, comprehensive_id: int, audio: AudioFile, filename: str | None, version: str | None
) -> Json:
    headers = {"Content-Type": audio.content_type}
    if name := header_filename(filename or audio.filename):
        headers["X-Filename"] = name
    item = await api.request(
        "PUT", f"/comprehensives/{comprehensive_id}/audio", content=audio.content, headers=headers, version=version
    )
    return _without_html(item)


def main() -> None:
    """Console entry point: serve over stdio."""
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        raise SystemExit(f"lj-mcp: {exc}") from None
    build_server(settings).run("stdio")
