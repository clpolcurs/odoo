"""Odoo records -> API v1 objects (see static/api/openapi.yaml).

The API names are the contract; Odoo field names stay behind this module.
Every object gets a `version`: a hash of its content, without timestamps.
"""

import hashlib
import json
import re

from odoo import fields

from . import markup as markup_lib

API_PREFIX = "/api/lj/v1"
LEVELS = ["N5", "N4", "N3", "N2", "N1"]

_RE_FILTER_PREFIX = re.compile(r"^\s*(?:\[[^\]]*\]\s*)+")

VERB_FORM_FIELDS = {
    "dictionary": "the_tu_dien",
    "past": "the_qua_khu",
    "negative": "the_phu_dinh",
    "te": "the_te",
    "potential": "the_kha_nang",
    "passive": "the_thu_dong",
    "causative": "the_sai_khien",
    "causative_passive": "the_sai_khien_thu_dong",
    "conditional": "the_dieu_kien",
    "imperative": "the_menh_lenh",
    "volitional": "the_y_chi",
    "prohibitive": "the_cam_chi",
}
VERB_GROUPS = {"nhom_1": "group1", "nhom_2": "group2", "nhom_3": "group3"}
HONORIFIC_TYPES = {"kinh_ngu": "sonkeigo", "khiem_nhuong_ngu": "kenjougo"}


def version_of(data):
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def with_version(data, volatile=("created_at", "updated_at")):
    data["version"] = version_of({k: v for k, v in data.items() if k not in volatile})
    return data


def iso(value):
    """Odoo UTC datetime -> '2026-10-26T15:04:05Z'."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def xid(entity, record_id):
    return f"odoo:{entity}:{record_id}"


def display_title(title):
    """Drop leading `[...]` filter prefixes; usage prefixes such as `PI` or `thể ta` stay."""
    return _RE_FILTER_PREFIX.sub("", title or "").strip()


def patterns_of(text):
    seen, patterns = set(), []
    for line in (text or "").splitlines():
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            patterns.append(line)
    return patterns


def _html(value):
    return str(value) if value else None


# ── Comprehensive ──────────────────────────────────────────────────────────────

def audio_index(env, items):
    """{item id: Audio object} for the items that have an audio file (one query)."""
    if not items:
        return {}
    attachments = env["ir.attachment"].sudo().search_read(
        [("res_model", "=", items._name), ("res_field", "=", "audio_file"), ("res_id", "in", items.ids)],
        ["res_id", "checksum", "file_size", "mimetype", "name"],
    )
    return {
        att["res_id"]: {
            "url": f"{API_PREFIX}/comprehensives/{att['res_id']}/audio",
            "sha1": att["checksum"],
            "size": att["file_size"],
            "mimetype": att["mimetype"],
            "filename": att["name"] if att["name"] != "audio_file" else None,
        }
        for att in attachments
    }


def comprehensives(items, view="full"):
    audio = audio_index(items.env, items)
    return [comprehensive(item, view, audio.get(item.id)) for item in items]


def comprehensive(item, view="full", audio=None):
    source = markup_lib.to_source(item.backup_text)
    data = {
        "id": item.id,
        "xid": xid("comprehensive", item.id),
        "title": item.title or "",
        "title_display": display_title(item.title),
        "level": item.level or None,
        "tags": sorted(item.category_ids.mapped("name")),
        "lesson_ids": sorted(item.lesson_ids.ids),
        "book_ids": sorted(item.book_ids.ids),
        "published": item.nihongo_published,
        "has_markup": markup_lib.has_markup(source),
        "audio": audio,
        "markup": source,
        "html_hover": _html(item.content_only_kanji),
        "html_ruby": _html(item.content),
        "is_finalized": item.is_finalized,
        "description": item.description or None,
        "grammar_patterns": patterns_of(item.grammar_patterns),
        "grammar_overrides": grammar_overrides(item),
        "created_at": iso(item.create_date),
        "updated_at": iso(item.write_date),
    }
    with_version(data)
    if view == "summary":
        for key in ("markup", "html_hover", "html_ruby", "is_finalized", "description",
                    "grammar_patterns", "grammar_overrides", "created_at"):
            data.pop(key)
    return data


def grammar_overrides(item):
    return [
        {
            "grammar_id": override.grammar_id.id,
            "grammar_title": override.grammar_id.title or "",
            "action": override.action,
            "note": override.note or None,
        }
        for override in item.grammar_override_ids.sorted("grammar_id")
    ]


# ── Vocabulary ─────────────────────────────────────────────────────────────────

def vocabulary(record):
    data = {
        "id": record.id,
        "xid": xid("vocabulary", record.id),
        "term": record.vocabulary or "",
        "hiragana": record.higarana or None,
        "katakana": record.katakana or None,
        "romaji": record.romanji or None,
        "meaning_vi": record.vietnamese or None,
        "han_viet": record.han_viet or None,
        "level": record.level or None,
        "is_intransitive": record.is_intransitive,
        "is_verb": record.is_verb,
        "verb_group": VERB_GROUPS.get(record.nhom_dong_tu),
        "honorific_type": HONORIFIC_TYPES.get(record.nhom_ngu),
        "forms": {name: record[field] or None for name, field in VERB_FORM_FIELDS.items()},
        "part_of_speech_ids": sorted(record.part_of_speech_ids.ids),
        "context_tag_ids": sorted(record.context_tag_ids.ids),
        "lesson_ids": sorted(record.lesson_ids.ids),
        "book_ids": sorted(record.book_ids.ids),
        "published": record.nihongo_published,
        "examples_markup": markup_lib.to_source(record.backup_text),
        "examples_html_ruby": _html(record.content),
        "created_at": iso(record.create_date),
        "updated_at": iso(record.write_date),
    }
    return with_version(data)


# ── Books, lessons ─────────────────────────────────────────────────────────────

def lesson_name(lesson):
    return lesson.lesson or lesson.combination or ""


def member_counts(env, lesson_ids):
    """{lesson id: (item count, vocabulary count)}."""
    counts = {lesson_id: [0, 0] for lesson_id in lesson_ids}
    if not lesson_ids:
        return counts
    cr = env.cr
    env.flush_all()
    for column, table, position in (
        ("lesson_id", "comprehensive_lesson_rel", 0),
        ("lesson_id", "lesson_vocabulary_rel", 1),
    ):
        cr.execute(
            f"SELECT {column}, count(*) FROM {table} WHERE {column} = ANY(%s) GROUP BY {column}",
            [list(lesson_ids)],
        )
        for lesson_id, count in cr.fetchall():
            counts[lesson_id][position] = count
    return counts


def books(records):
    counts = member_counts(records.env, records.lesson_ids.ids)
    return [book(record, counts) for record in records]


def book(record, counts=None):
    if counts is None:
        counts = member_counts(record.env, record.lesson_ids.ids)
    lessons = record.lesson_ids.sorted("id")
    data = {
        "id": record.id,
        "xid": xid("book", record.id),
        "name": record.name or "",
        "published": record.nihongo_published,
        "lessons": [{"id": lesson.id, "xid": xid("lesson", lesson.id), "name": lesson_name(lesson)} for lesson in lessons],
        "updated_at": iso(record.write_date),
    }
    with_version(data)
    # Counts move with membership changes owned by the items, so they stay out of `version`.
    for entry in data["lessons"]:
        entry["item_count"], entry["vocabulary_count"] = counts.get(entry["id"], (0, 0))
    return data


def lessons(records):
    counts = member_counts(records.env, records.ids)
    return [lesson(record, counts) for record in records]


def lesson(record, counts=None):
    if counts is None:
        counts = member_counts(record.env, record.ids)
    data = with_version({
        "id": record.id,
        "xid": xid("lesson", record.id),
        "name": lesson_name(record),
        "book_id": record.book_id.id or None,
        "published": record.book_id.nihongo_published,
        "updated_at": iso(record.write_date),
    })
    data["item_count"], data["vocabulary_count"] = counts.get(record.id, (0, 0))
    return data


# ── Catalogs ───────────────────────────────────────────────────────────────────

def tag(record):
    return with_version({"id": record.id, "xid": xid("tag", record.id), "name": record.name or "", "color": record.color or None})


def context_tag(record):
    return with_version({
        "id": record.id,
        "xid": xid("context_tag", record.id),
        "name": record.name or "",
        "complete_name": record.complete_name or None,
        "parent_id": record.parent_id.id or None,
    })


def part_of_speech(record):
    return with_version({
        "id": record.id,
        "xid": xid("part_of_speech", record.id),
        "kanji": record.kanji or None,
        "hiragana": record.higarana or None,
        "vietnamese": record.vietnamese or None,
        "label": record.combination or None,
    })


def hanviet(record):
    return with_version({"id": record.id, "xid": xid("hanviet", record.id), "kanji": record.kanji or None, "han_viet": record.han_viet or None})


def now_iso():
    return iso(fields.Datetime.now())
