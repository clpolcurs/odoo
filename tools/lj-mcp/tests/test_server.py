import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from helpers import API, FakeApi, call, call_error, mcp_session, problem

from lj_mcp.config import Settings

pytestmark = pytest.mark.anyio

READ_ONLY_TOOLS = {
    "lj_search_comprehensives",
    "lj_get_comprehensive",
    "lj_list_books",
    "lj_get_book",
    "lj_search_grammar",
    "lj_search_vocabulary",
    "lj_get_vocabulary",
    "lj_preview_markup",
    "lj_list_issues",
    "lj_list_catalog",
}
WRITE_TOOLS = {
    "lj_create_comprehensive",
    "lj_update_comprehensive",
    "lj_set_audio_from_url",
    "lj_set_audio_from_file",
    "lj_create_vocabulary",
    "lj_update_vocabulary",
    "lj_bulk_update_vocabulary",
    "lj_link_lesson",
    "lj_set_grammar_patterns",
    "lj_set_grammar_overrides",
}
DELETE_TOOLS = {"lj_delete_comprehensive", "lj_delete_vocabulary"}

ITEM = {
    "id": 58,
    "xid": "odoo:comprehensive:58",
    "title": "[Cơ bản] そうですね",
    "title_display": "そうですね",
    "level": "N2",
    "tags": ["Listening"],
    "lesson_ids": [12],
    "book_ids": [3],
    "published": True,
    "has_markup": True,
    "audio": None,
    "updated_at": "2026-10-26T15:04:05Z",
    "version": "v1",
    "markup": "<p><<人 - ひと>>と{{người}}</p>",
    "html_hover": "<p>…</p>",
    "html_ruby": "<div>…</div>",
    "is_finalized": True,
    "description": None,
    "grammar_patterns": [],
    "grammar_overrides": [],
    "created_at": "2026-10-01T08:00:00Z",
}
ITEM_WITHOUT_HTML = {key: value for key, value in ITEM.items() if key not in ("html_hover", "html_ruby")}
WITH_DELETE = Settings(base_url="https://lj.test", api_key="secret-key", allow_delete=True)


def body(request: httpx.Request) -> Any:
    return json.loads(request.content)


async def test_lists_the_tools_without_delete_by_default(fake: FakeApi) -> None:
    async with mcp_session(fake) as session:
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
    assert set(tools) == READ_ONLY_TOOLS | WRITE_TOOLS
    assert all(tools[name].annotations.readOnlyHint is True for name in READ_ONLY_TOOLS)
    assert all(tools[name].annotations.readOnlyHint is False for name in WRITE_TOOLS)
    assert all(tools[name].annotations.destructiveHint is False for name in WRITE_TOOLS)
    assert "version" in tools["lj_get_comprehensive"].description


async def test_allow_delete_adds_the_delete_tools(fake: FakeApi) -> None:
    settings = Settings.from_env({"LJ_BASE_URL": "https://lj.test", "LJ_API_KEY": "secret-key", "LJ_ALLOW_DELETE": "1"})
    async with mcp_session(fake, settings) as session:
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
    assert set(tools) == READ_ONLY_TOOLS | WRITE_TOOLS | DELETE_TOOLS
    assert all(tools[name].annotations.destructiveHint is True for name in DELETE_TOOLS)


async def test_delete_sends_if_match(fake: FakeApi) -> None:
    fake.on("DELETE", f"{API}/vocabularies/120", lambda request: httpx.Response(204))
    async with mcp_session(fake, WITH_DELETE) as session:
        assert await call(session, "lj_delete_vocabulary", vocabulary_id=120, version="a1") == {
            "id": 120,
            "deleted": True,
        }
    assert fake.requests[0].headers["If-Match"] == '"a1"'


async def test_without_api_key_requests_carry_no_authorization(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/comprehensives", lambda request: httpx.Response(401, html="<h1>Unauthorized</h1>"))
    async with mcp_session(fake, Settings(base_url="https://lj.test")) as session:
        assert len((await session.list_tools()).tools) == len(READ_ONLY_TOOLS | WRITE_TOOLS)
        message = await call_error(session, "lj_search_comprehensives")
    assert "Authorization" not in fake.requests[0].headers
    assert "HTTP 401: Unauthorized" in message
    assert "network secret" in message


async def test_get_comprehensive_returns_the_api_json_compactly_without_html(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/comprehensives/58", ITEM)
    async with mcp_session(fake) as session:
        result = await session.call_tool("lj_get_comprehensive", {"comprehensive_id": 58})
        with_html = await call(session, "lj_get_comprehensive", comprehensive_id=58, include_html=True)
    assert not result.isError
    assert result.structuredContent is None
    assert result.content[0].text == json.dumps(ITEM_WITHOUT_HTML, ensure_ascii=False, separators=(",", ":"))
    assert with_html == ITEM


async def test_preview_markup_leaves_out_the_html_unless_asked(fake: FakeApi) -> None:
    preview = {"html_hover": "<p>…</p>", "html_ruby": "<div>…</div>", "stats": {"markers": 1}, "issues": []}
    fake.on("POST", f"{API}/markup/preview", preview)
    async with mcp_session(fake) as session:
        assert await call(session, "lj_preview_markup", markup="<p><<人 - ひと>></p>") == {
            "stats": {"markers": 1},
            "issues": [],
        }
        assert await call(session, "lj_preview_markup", markup="<p><<人 - ひと>></p>", include_html=True) == preview


async def test_write_tools_return_the_item_without_html(fake: FakeApi) -> None:
    fake.on("POST", f"{API}/comprehensives", ITEM)
    fake.on("PATCH", f"{API}/comprehensives/58", ITEM | {"version": "v2"})
    async with mcp_session(fake) as session:
        assert await call(session, "lj_create_comprehensive", title="そうですね") == ITEM_WITHOUT_HTML
        updated = await call(session, "lj_update_comprehensive", comprehensive_id=58, version="v1", level="N3")
        patterns = await call(session, "lj_set_grammar_patterns", comprehensive_id=58, version="v2", patterns=[])
    assert updated == patterns == ITEM_WITHOUT_HTML | {"version": "v2"}


async def test_api_errors_become_tool_errors(fake: FakeApi) -> None:
    fake.on(
        "PATCH",
        f"{API}/comprehensives/58",
        lambda request: problem(
            412, "version-mismatch", "The record changed since that version.", current_version="v2"
        ),
    )
    async with mcp_session(fake) as session:
        message = await call_error(session, "lj_update_comprehensive", comprehensive_id=58, version="v1", title="x")
    assert "HTTP 412 version-mismatch: The record changed since that version." in message
    assert "current_version: v2" in message


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "path", "query", "sent", "if_match"),
    [
        (
            "lj_search_comprehensives",
            {"q": "そう", "level": "N3,N2", "tag": "Listening", "lesson_id": 12, "published": False, "cursor": "c1"},
            "GET",
            "/comprehensives",
            {
                "q": "そう",
                "level": "N3,N2",
                "tag": "Listening",
                "lesson_id": "12",
                "published": "false",
                "limit": "50",
                "cursor": "c1",
                "view": "summary",
            },
            None,
            None,
        ),
        (
            "lj_search_grammar",
            {"q": "とする", "level": "N2", "limit": 10},
            "GET",
            "/comprehensives",
            {"grammar": "true", "q": "とする", "level": "N2", "limit": "10", "view": "summary"},
            None,
            None,
        ),
        (
            "lj_list_books",
            {"published": True},
            "GET",
            "/books",
            {"published": "true", "limit": "50"},
            None,
            None,
        ),
        (
            "lj_search_vocabulary",
            {"q": "理解", "context_tag_id": 4},
            "GET",
            "/vocabularies",
            {"q": "理解", "context_tag_id": "4", "limit": "50"},
            None,
            None,
        ),
        ("lj_get_vocabulary", {"vocabulary_id": 120}, "GET", "/vocabularies/120", {}, None, None),
        (
            "lj_list_issues",
            {"code": "auto_readings,missing_audio", "book_id": 3},
            "GET",
            "/qa/issues",
            {"code": "auto_readings,missing_audio", "book_id": "3", "limit": "50"},
            None,
            None,
        ),
        (
            "lj_preview_markup",
            {"markup": "<p><<人 - ひと>>{{người}}</p>"},
            "POST",
            "/markup/preview",
            {},
            {"markup": "<p><<人 - ひと>>{{người}}</p>"},
            None,
        ),
        ("lj_list_catalog", {"catalog": "tags"}, "GET", "/tags", {"limit": "200"}, None, None),
        (
            "lj_list_catalog",
            {"catalog": "lessons", "book_id": 3, "limit": 50},
            "GET",
            "/lessons",
            {"book_id": "3", "limit": "50"},
            None,
            None,
        ),
        (
            "lj_list_catalog",
            {"catalog": "context_tags", "cursor": "c1"},
            "GET",
            "/context-tags",
            {"limit": "200", "cursor": "c1"},
            None,
            None,
        ),
        ("lj_list_catalog", {"catalog": "parts_of_speech"}, "GET", "/parts-of-speech", {"limit": "200"}, None, None),
        (
            "lj_list_catalog",
            {"catalog": "hanviet", "kanji": "理解"},
            "GET",
            "/hanviet",
            {"kanji": "理解", "limit": "200"},
            None,
            None,
        ),
        (
            "lj_create_comprehensive",
            {"title": "読解 1", "level": "N3", "tags": ["Reading"], "lesson_ids": [12]},
            "POST",
            "/comprehensives",
            {},
            {"title": "読解 1", "level": "N3", "tags": ["Reading"], "lesson_ids": [12]},
            None,
        ),
        (
            "lj_create_vocabulary",
            {"term": "理解します", "hiragana": "りかいします", "verb_group": "group3", "forms": {"te": "理解して"}},
            "POST",
            "/vocabularies",
            {},
            {"term": "理解します", "hiragana": "りかいします", "verb_group": "group3", "forms": {"te": "理解して"}},
            None,
        ),
        (
            "lj_update_vocabulary",
            {"vocabulary_id": 120, "version": "a1", "meaning_vi": "hiểu", "level": "none"},
            "PATCH",
            "/vocabularies/120",
            {},
            {"meaning_vi": "hiểu", "level": None},
            '"a1"',
        ),
        (
            "lj_set_grammar_patterns",
            {"comprehensive_id": 7, "version": "g1", "patterns": ["とする", "としても"]},
            "PATCH",
            "/comprehensives/7",
            {},
            {"grammar_patterns": ["とする", "としても"]},
            '"g1"',
        ),
        (
            "lj_set_grammar_overrides",
            {"comprehensive_id": 58, "overrides": [{"grammar_id": 7, "action": "pin"}]},
            "PUT",
            "/comprehensives/58/grammar-overrides",
            {},
            {"items": [{"grammar_id": 7, "action": "pin", "note": None}]},
            None,
        ),
    ],
)
async def test_tools_send_the_documented_requests(
    fake: FakeApi,
    tool: str,
    arguments: dict[str, Any],
    method: str,
    path: str,
    query: dict[str, str],
    sent: Any,
    if_match: str | None,
) -> None:
    fake.on(method, API + path, {"ok": True})
    async with mcp_session(fake) as session:
        assert await call(session, tool, **arguments) == {"ok": True}
    (request,) = fake.requests
    assert dict(request.url.params) == query
    assert (body(request) if request.content else None) == sent
    assert request.headers.get("If-Match") == if_match


async def test_list_catalog_rejects_a_filter_of_another_catalog(fake: FakeApi) -> None:
    async with mcp_session(fake) as session:
        assert "book_id only applies" in await call_error(session, "lj_list_catalog", catalog="tags", book_id=3)
        assert "kanji only applies" in await call_error(session, "lj_list_catalog", catalog="lessons", kanji="理")
    assert fake.requests == []


async def test_update_comprehensive_sends_only_the_given_fields(fake: FakeApi) -> None:
    fake.on("PATCH", f"{API}/comprehensives/58", ITEM | {"level": None, "version": "v2"})
    async with mcp_session(fake) as session:
        result = await call(
            session, "lj_update_comprehensive", comprehensive_id=58, version="v1", level="none", description=""
        )
    assert result["version"] == "v2"
    (request,) = fake.requests
    assert body(request) == {"level": None, "description": ""}
    assert request.headers["If-Match"] == '"v1"'


async def test_update_needs_a_field_to_change(fake: FakeApi) -> None:
    async with mcp_session(fake) as session:
        message = await call_error(session, "lj_update_comprehensive", comprehensive_id=58, version="v1")
    assert "nothing to update" in message
    assert fake.requests == []


async def test_link_lesson_saves_with_the_version_just_read(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/comprehensives/58", ITEM)
    fake.on("PATCH", f"{API}/comprehensives/58", ITEM | {"lesson_ids": [12, 15], "version": "v2"})
    async with mcp_session(fake) as session:
        result = await call(session, "lj_link_lesson", comprehensive_id=58, lesson_id=15)
    assert result["lesson_ids"] == [12, 15]
    read, patch = fake.requests
    assert (read.method, patch.method) == ("GET", "PATCH")
    assert body(patch) == {"lesson_ids": [12, 15]}
    assert patch.headers["If-Match"] == '"v1"'


async def test_link_lesson_removes_one_lesson(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/comprehensives/58", ITEM | {"lesson_ids": [12, 15, 16]})
    fake.on("PATCH", f"{API}/comprehensives/58", ITEM | {"lesson_ids": [12, 16], "version": "v2"})
    async with mcp_session(fake) as session:
        await call(session, "lj_link_lesson", comprehensive_id=58, lesson_id=15, action="remove")
    assert body(fake.requests[1]) == {"lesson_ids": [12, 16]}


async def test_link_lesson_with_a_stale_version_surfaces_the_412(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/comprehensives/58", ITEM)
    fake.on(
        "PATCH",
        f"{API}/comprehensives/58",
        lambda request: problem(412, "version-mismatch", "The record changed.", current_version="v1"),
    )
    async with mcp_session(fake) as session:
        message = await call_error(session, "lj_link_lesson", comprehensive_id=58, lesson_id=15, version="v0")
    assert fake.requests[1].headers["If-Match"] == '"v0"'
    assert "HTTP 412 version-mismatch" in message
    assert "current_version: v1" in message


async def test_link_lesson_writes_nothing_when_already_linked(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/comprehensives/58", ITEM)
    async with mcp_session(fake) as session:
        assert await call(session, "lj_link_lesson", comprehensive_id=58, lesson_id=12) == ITEM_WITHOUT_HTML
    assert [request.method for request in fake.requests] == ["GET"]


async def test_get_book_includes_all_its_items(fake: FakeApi) -> None:
    book = {"id": 3, "name": "ドリル&ドリル N2", "lessons": [{"id": 12, "name": "聴解・課題理解"}], "version": "b1"}
    pages = {None: ([{"id": 58}], "c2"), "c2": ([{"id": 59}], None)}

    def page(request: httpx.Request) -> httpx.Response:
        items, next_cursor = pages[request.url.params.get("cursor")]
        return httpx.Response(200, json={"items": items, "next_cursor": next_cursor})

    fake.on("GET", f"{API}/books/3", book)
    fake.on("GET", f"{API}/comprehensives", page)
    async with mcp_session(fake) as session:
        result = await call(session, "lj_get_book", book_id=3)
    assert result == {"book": book, "items": [{"id": 58}, {"id": 59}], "next_cursor": None}
    first_page = fake.requests[1].url.params
    assert (first_page["book_id"], first_page["view"], first_page["limit"]) == ("3", "summary", "100")


async def test_set_audio_from_url_uploads_the_download(fake: FakeApi) -> None:
    url = "https://files.test/audio/n2-dd-1ban.mp3"
    fake.on(
        "GET", url, lambda request: httpx.Response(200, headers={"Content-Type": "audio/mpeg"}, content=b"ID3 data")
    )
    fake.on("PUT", f"{API}/comprehensives/58/audio", ITEM | {"version": "v2"})
    async with mcp_session(fake) as session:
        result = await call(session, "lj_set_audio_from_url", comprehensive_id=58, url=url, version="v1")
    assert result["version"] == "v2"
    download, upload = fake.requests
    assert "Authorization" not in download.headers  # the API key never goes to other hosts
    assert upload.content == b"ID3 data"
    assert upload.headers["Content-Type"] == "audio/mpeg"
    assert upload.headers["X-Filename"] == "n2-dd-1ban.mp3"
    assert upload.headers["If-Match"] == '"v1"'
    assert upload.headers["Authorization"] == "Bearer secret-key"


async def test_set_audio_from_url_uploads_nothing_that_is_not_audio(fake: FakeApi) -> None:
    fake.on("GET", "https://drive.test/file/d/1/view", lambda request: httpx.Response(200, html="<html></html>"))
    async with mcp_session(fake) as session:
        message = await call_error(
            session, "lj_set_audio_from_url", comprehensive_id=58, url="https://drive.test/file/d/1/view"
        )
    assert "is not audio" in message
    assert [request.method for request in fake.requests] == ["GET"]


async def test_set_audio_from_file_uploads_the_file(fake: FakeApi, tmp_path: Path) -> None:
    file = tmp_path / "聴解.wav"
    file.write_bytes(b"RIFF data")
    fake.on("PUT", f"{API}/comprehensives/58/audio", ITEM | {"version": "v2"})
    async with mcp_session(fake) as session:
        await call(session, "lj_set_audio_from_file", comprehensive_id=58, path=str(file))
    (upload,) = fake.requests
    assert upload.content == b"RIFF data"
    assert upload.headers["Content-Type"] == "audio/wav"
    assert upload.headers["X-Filename"] == "%E8%81%B4%E8%A7%A3.wav"
    assert "If-Match" not in upload.headers


async def test_bulk_update_vocabulary_sends_only_the_given_fields(fake: FakeApi) -> None:
    fake.on("POST", f"{API}/vocabularies/bulk", {"items": []})
    entries = [
        {"id": 120, "version": "a1", "meaning_vi": "hiểu", "level": "none"},
        {"term": "元々", "hiragana": "もともと", "forms": {"te": None}},
        {"id": 121, "katakana": None},
    ]
    async with mcp_session(fake) as session:
        await call(session, "lj_bulk_update_vocabulary", items=entries)
    assert body(fake.requests[0]) == {
        "items": [
            {"id": 120, "version": "a1", "meaning_vi": "hiểu", "level": None},
            {"term": "元々", "hiragana": "もともと", "forms": {"te": None}},
            {"id": 121, "katakana": None},
        ]
    }


async def test_bulk_update_vocabulary_limits_and_entry_errors(fake: FakeApi) -> None:
    errors = [{"index": 1, "field": "term", "message": "required to create"}]
    fake.on(
        "POST",
        f"{API}/vocabularies/bulk",
        lambda request: problem(422, "validation-error", "1 entry is invalid", errors=errors),
    )
    async with mcp_session(fake) as session:
        too_many = await call_error(session, "lj_bulk_update_vocabulary", items=[{"term": "語"}] * 101)
        assert fake.requests == []
        message = await call_error(session, "lj_bulk_update_vocabulary", items=[{"id": 120}, {"hiragana": "ご"}])
    assert "at most 100" in too_many
    assert "HTTP 422 validation-error: 1 entry is invalid" in message
    assert "- index 1, field term: required to create" in message


async def test_prompts(fake: FakeApi) -> None:
    async with mcp_session(fake) as session:
        names = {prompt.name for prompt in (await session.list_prompts()).prompts}
        annotate = await session.get_prompt("annotate_japanese_text", {"text": "女の人が来ました。", "level": "N4"})
        review = await session.get_prompt("review_readings", {"comprehensive_id": "58"})
    assert names == {"annotate_japanese_text", "review_readings"}
    annotate_text = annotate.messages[0].content.text
    assert "<<女 - おんな>>の<<人 - ひと>>" in annotate_text
    assert "<<1人 - ひとり>>" in annotate_text
    assert "{{...}}" in annotate_text
    assert "lj_preview_markup" in annotate_text
    assert "Trình độ JLPT: N4" in annotate_text
    assert annotate_text.endswith("女の人が来ました。")
    review_text = review.messages[0].content.text
    assert "lj_get_comprehensive(comprehensive_id=58)" in review_text
    assert "係りの人" in review_text
    assert "lj_update_comprehensive" in review_text
