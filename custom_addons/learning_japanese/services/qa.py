"""GET /qa/issues: what to fix in Odoo (through MCP) before content goes to NihonGo."""

from . import markup as markup_lib
from . import serializers
from .content_service import (
    COMPREHENSIVE,
    decode_cursor,
    encode_cursor,
    level_domain,
    parse_bool,
    parse_csv,
    parse_int,
    parse_levels,
    parse_limit,
    tag_ids,
)
from .errors import bad_request

CODES = [
    "missing_level",
    "missing_markup",
    "not_finalized",
    "unbalanced_markup",
    "kanji_without_reading",
    "auto_readings",
    "untagged_translation",
    "missing_audio",
    "grammar_missing_patterns",
    "not_published",
]
# not_published describes most items before the first sync, so it is only listed on request.
DEFAULT_CODES = [code for code in CODES if code != "not_published"]
DEFAULT_TAGS = ["Reading", "Listening", "Grammar"]
DETAILS_MAX = 20


def list_issues(env, params):
    codes = parse_csv(params, "code") or DEFAULT_CODES
    unknown = [code for code in codes if code not in CODES]
    if unknown:
        raise bad_request(f"Unknown issue code {unknown[0]!r}; known codes: {', '.join(CODES)}.")

    domain = level_domain(parse_levels(params))
    domain.append(("category_ids", "in", tag_ids(env, parse_csv(params, "tag") or DEFAULT_TAGS)))
    if (book_id := parse_int(params, "book_id")) is not None:
        domain.append(("book_ids", "in", [book_id]))
    if (published := parse_bool(params, "published")) is not None:
        domain.append(("nihongo_published", "=", published))

    items = env[COMPREHENSIVE].search(domain, order="id")
    audio = serializers.audio_index(env, items)
    summary = dict.fromkeys(codes, 0)
    flagged = []
    for item in items:
        issues = [issue for issue in item_issues(item, item.id in audio) if issue["code"] in summary]
        if issues:
            flagged.append((item, issues))
            for issue in issues:
                summary[issue["code"]] += 1

    limit = parse_limit(params)
    after = decode_cursor(params.get("cursor"))
    page = [entry for entry in flagged if entry[0].id > after]
    next_cursor = encode_cursor(page[limit - 1][0].id) if len(page) > limit else None
    return {
        "items": [
            {
                "entity": "comprehensive",
                "id": item.id,
                "title": item.title or "",
                "level": item.level or None,
                "tags": sorted(item.category_ids.mapped("name")),
                "book_ids": sorted(item.book_ids.ids),
                "published": item.nihongo_published,
                "issues": issues,
            }
            for item, issues in page[:limit]
        ],
        "summary": summary,
        "next_cursor": next_cursor,
    }


def item_issues(item, has_audio):
    tags = {name.lower() for name in item.category_ids.mapped("name")}
    issues = []
    if not item.level:
        issues.append({"code": "missing_level"})

    source = markup_lib.to_source(item.backup_text)
    if markup_lib.has_markup(source):
        found = markup_lib.analyze(source)["issues"]
        unbalanced = [i for i in found if i["code"] in ("unbalanced_marker", "unbalanced_translation")]
        if unbalanced:
            issues.append({"code": "unbalanced_markup", "count": len(unbalanced)})
        outside = [i["text"] for i in found if i["code"] == "kanji_without_reading"]
        if outside:
            issues.append({"code": "kanji_without_reading", "count": len(outside), "details": _unique(outside)})
        guessed = [f"{i['text']} → {i['reading']}" for i in found if i["code"] == "auto_reading"]
        if guessed:
            issues.append({"code": "auto_readings", "count": len(guessed), "details": _unique(guessed)})
        untagged = [_short(i["text"]) for i in found if i["code"] == "untagged_translation"]
        if untagged:
            issues.append({"code": "untagged_translation", "count": len(untagged), "details": _unique(untagged)})
        if not item.is_finalized:
            issues.append({"code": "not_finalized"})
    elif tags & {"reading", "listening"}:
        issues.append({"code": "missing_markup"})

    if "listening" in tags and not has_audio:
        issues.append({"code": "missing_audio"})
    if item.is_grammar and not serializers.patterns_of(item.grammar_patterns):
        issues.append({"code": "grammar_missing_patterns"})
    if not item.nihongo_published:
        issues.append({"code": "not_published"})
    return issues


def _unique(values):
    return list(dict.fromkeys(values))[:DETAILS_MAX]


def _short(text, width=60):
    return text if len(text) <= width else text[: width - 1] + "…"
