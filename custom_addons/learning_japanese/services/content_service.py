"""Reads and writes behind API v1. Controllers only map HTTP to these functions."""

import base64
import binascii
import os
from datetime import datetime, timezone

import psycopg2

from odoo.fields import Command

from . import markup as markup_lib
from . import serializers
from .errors import ApiError, bad_request, invalid, not_found

API_VERSION = "1.0.0"
READ_GROUP = "learning_japanese.learning_japanese_view_only_group"
WRITE_GROUP = "learning_japanese.learning_japanese_admin"

PAGE_DEFAULT, PAGE_MAX = 50, 200
IDS_MAX = 200
BULK_MAX = 100
OVERRIDES_MAX = 200
MARKUP_MAX = 200_000
AUDIO_MAX_BYTES = 30 * 1024 * 1024

COMPREHENSIVE = "learning_japanese.comprehensive"
VOCABULARY = "learning_japanese.vocabulary"
BOOK = "learning_japanese.book"
LESSON = "learning_japanese.lesson"
TAG = "learning_japanese.comprehensive_tag"


# ── Request parsing ────────────────────────────────────────────────────────────

def encode_cursor(last_id):
    return base64.urlsafe_b64encode(f"id:{last_id}".encode()).decode().rstrip("=")


def decode_cursor(cursor):
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        prefix, _, value = raw.partition(":")
        if prefix == "id" and value.isdigit():
            return int(value)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        pass
    raise bad_request("Invalid cursor.")


def parse_limit(params, default=PAGE_DEFAULT, maximum=PAGE_MAX):
    value = params.get("limit")
    if value in (None, ""):
        return default
    if not str(value).isdigit() or not 1 <= int(value) <= maximum:
        raise bad_request(f"limit must be an integer between 1 and {maximum}.")
    return int(value)


def parse_int(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    if not str(value).isdigit():
        raise bad_request(f"{name} must be a positive integer.")
    return int(value)


def parse_bool(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    lowered = str(value).lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise bad_request(f"{name} must be true or false.")


def parse_csv(params, name):
    return [part.strip() for part in (params.get(name) or "").split(",") if part.strip()]


def parse_ids(params, name="ids"):
    values = parse_csv(params, name)
    if not all(value.isdigit() for value in values):
        raise bad_request(f"{name} must be comma separated integers.")
    if len(values) > IDS_MAX:
        raise bad_request(f"At most {IDS_MAX} ids.")
    return [int(value) for value in values]


def parse_levels(params):
    values = parse_csv(params, "level")
    unknown = [v for v in values if v != "none" and v not in serializers.LEVELS]
    if unknown:
        raise bad_request(f"Unknown level {unknown[0]!r}; use N5, N4, N3, N2, N1 or none.")
    return values


def parse_datetime(params, name):
    value = params.get(name)
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise bad_request(f"{name} must be an ISO-8601 date-time.") from None
    if moment.tzinfo:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def level_domain(levels):
    if not levels:
        return []
    named = [level for level in levels if level != "none"]
    if "none" in levels and named:
        return ["|", ("level", "=", False), ("level", "in", named)]
    if "none" in levels:
        return [("level", "=", False)]
    return [("level", "in", named)]


def tag_ids(env, names, field="tag"):
    """Tag names (case-insensitive) -> ids; unknown names are a 400."""
    if not names:
        return []
    by_name = {tag.name.lower(): tag.id for tag in env[TAG].search([]) if tag.name}
    unknown = [name for name in names if name.lower() not in by_name]
    if unknown:
        raise bad_request(f"Unknown {field} {unknown[0]!r}; see GET /tags.")
    return [by_name[name.lower()] for name in names]


def paginate(model, domain, params, default=PAGE_DEFAULT, maximum=PAGE_MAX):
    limit = parse_limit(params, default, maximum)
    after = decode_cursor(params.get("cursor"))
    records = model.search(domain + [("id", ">", after)], order="id", limit=limit + 1)
    next_cursor = encode_cursor(records[limit - 1].id) if len(records) > limit else None
    return records[:limit], next_cursor


def check_version(current, if_match, required=True):
    if not if_match:
        if required:
            raise ApiError(428, "version-required", "Send If-Match with the version you read.")
        return
    versions = {value.strip().removeprefix("W/").strip('"') for value in if_match.split(",")}
    if "*" not in versions and current not in versions:
        raise ApiError(412, "version-mismatch", "The record changed since you read it.", current_version=current)


def audit(env, entity, res_id, op, before=None, after=None):
    env["learning_japanese.audit_log"]._log(entity, res_id, op, before, after)


def _get(env, model, record_id, entity):
    record = env[model].browse(record_id).exists()
    if not record:
        raise not_found(entity, record_id)
    return record


# ── Meta, books, lessons, catalogs ─────────────────────────────────────────────

def meta(env):
    user = env.user
    return {
        "api_version": API_VERSION,
        "server_time": serializers.now_iso(),
        "user": {"id": user.id, "login": user.login, "can_write": user.has_group(WRITE_GROUP)},
        "levels": serializers.LEVELS,
        "tags": [serializers.tag(tag) for tag in env[TAG].search([], order="id")],
        "limits": {
            "page_max": PAGE_MAX,
            "changes_max": 1000,
            "snapshot_max": 1000,
            "bulk_max": BULK_MAX,
            "audio_max_bytes": AUDIO_MAX_BYTES,
            "change_log_retention_days": 90,
        },
    }


def list_books(env, params):
    domain = []
    if ids := parse_ids(params):
        domain.append(("id", "in", ids))
    if (published := parse_bool(params, "published")) is not None:
        domain.append(("nihongo_published", "=", published))
    if q := (params.get("q") or "").strip():
        domain.append(("name", "ilike", q))
    records, next_cursor = paginate(env[BOOK], domain, params)
    return {"items": serializers.books(records), "next_cursor": next_cursor}


def get_book(env, book_id):
    return serializers.book(_get(env, BOOK, book_id, "Book"))


def list_lessons(env, params):
    domain = []
    if ids := parse_ids(params):
        domain.append(("id", "in", ids))
    if (book_id := parse_int(params, "book_id")) is not None:
        domain.append(("book_id", "=", book_id))
    records, next_cursor = paginate(env[LESSON], domain, params)
    return {"items": serializers.lessons(records), "next_cursor": next_cursor}


CATALOGS = {
    "tags": (TAG, serializers.tag),
    "context-tags": ("learning_japanese.context_tag", serializers.context_tag),
    "parts-of-speech": ("learning_japanese.part_of_speech", serializers.part_of_speech),
    "hanviet": ("learning_japanese.hanviet", serializers.hanviet),
}


def list_catalog(env, name, params):
    model, serialize = CATALOGS[name]
    domain = []
    if ids := parse_ids(params):
        domain.append(("id", "in", ids))
    if name == "hanviet" and (kanji := params.get("kanji")):
        domain.append(("kanji", "in", sorted(set(kanji))))
    records, next_cursor = paginate(env[model], domain, params)
    return {"items": [serialize(record) for record in records], "next_cursor": next_cursor}


# ── Comprehensives ─────────────────────────────────────────────────────────────

def comprehensive_domain(env, params):
    domain = level_domain(parse_levels(params))
    if ids := parse_ids(params):
        domain.append(("id", "in", ids))
    if names := parse_csv(params, "tag"):
        domain.append(("category_ids", "in", tag_ids(env, names)))
    if (book_id := parse_int(params, "book_id")) is not None:
        domain.append(("book_ids", "in", [book_id]))
    if (lesson_id := parse_int(params, "lesson_id")) is not None:
        domain.append(("lesson_ids", "in", [lesson_id]))
    if q := (params.get("q") or "").strip():
        domain += ["|", ("title", "ilike", q), ("description", "ilike", q)]
    if (published := parse_bool(params, "published")) is not None:
        domain.append(("nihongo_published", "=", published))
    if updated_after := parse_datetime(params, "updated_after"):
        domain.append(("write_date", ">", updated_after))
    return domain


def list_comprehensives(env, params):
    view = params.get("view") or "summary"
    if view not in ("summary", "full"):
        raise bad_request("view must be summary or full.")
    records, next_cursor = paginate(env[COMPREHENSIVE], comprehensive_domain(env, params), params)
    return {"items": serializers.comprehensives(records, view), "next_cursor": next_cursor}


def get_comprehensive(env, item_id):
    return serializers.comprehensives(_get(env, COMPREHENSIVE, item_id, "Comprehensive"))[0]


_COMPREHENSIVE_KEYS = {"title", "level", "tags", "lesson_ids", "markup", "description", "grammar_patterns"}


def _comprehensive_vals(env, body, creating):
    """Validated ORM values (without markup) and the markup value or None if absent."""
    if not isinstance(body, dict):
        raise bad_request("The body must be a JSON object.")
    if not creating and not body:
        raise bad_request("Nothing to update.")
    errors = [{"field": key, "message": "Unknown field."} for key in sorted(set(body) - _COMPREHENSIVE_KEYS)]
    vals = {}

    if "title" in body:
        title = body["title"]
        if not isinstance(title, str) or not title.strip() or len(title) > 1000:
            errors.append({"field": "title", "message": "A non-empty string of at most 1000 characters."})
        else:
            vals["title"] = title.strip()
    elif creating:
        errors.append({"field": "title", "message": "Required."})

    if "level" in body:
        if body["level"] is not None and body["level"] not in serializers.LEVELS:
            errors.append({"field": "level", "message": "One of N5, N4, N3, N2, N1 or null."})
        else:
            vals["level"] = body["level"] or False

    if "tags" in body:
        names = body["tags"]
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            errors.append({"field": "tags", "message": "A list of tag names."})
        else:
            try:
                vals["category_ids"] = [Command.set(tag_ids(env, names))]
            except ApiError as error:
                errors.append({"field": "tags", "message": error.detail})

    if "lesson_ids" in body:
        ids = body["lesson_ids"]
        if not _int_list(ids):
            errors.append({"field": "lesson_ids", "message": "A list of lesson ids."})
        else:
            missing = set(ids) - set(env[LESSON].browse(ids).exists().ids)
            if missing:
                errors.append({"field": "lesson_ids", "message": f"Unknown lessons {sorted(missing)}."})
            else:
                vals["lesson_ids"] = [Command.set(ids)]

    if "description" in body:
        if body["description"] is not None and not isinstance(body["description"], str):
            errors.append({"field": "description", "message": "A string or null."})
        else:
            vals["description"] = body["description"] or False

    if "grammar_patterns" in body:
        patterns = body["grammar_patterns"]
        if (not isinstance(patterns, list) or len(patterns) > 30
                or not all(isinstance(p, str) and 0 < len(p.strip()) <= 100 for p in patterns)):
            errors.append({"field": "grammar_patterns", "message": "At most 30 non-empty strings of 100 characters."})
        else:
            vals["grammar_patterns"] = "\n".join(serializers.patterns_of("\n".join(patterns))) or False

    markup = _markup_arg(body, "markup", errors)
    if errors:
        raise invalid(errors)
    return vals, markup


def _markup_arg(body, key, errors):
    if key not in body:
        return None
    value = body[key]
    if value is not None and not isinstance(value, str):
        errors.append({"field": key, "message": "A string or null."})
    elif value and len(value) > MARKUP_MAX:
        errors.append({"field": key, "message": f"At most {MARKUP_MAX} characters."})
    return value or ""


def _int_list(value):
    return isinstance(value, list) and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in value)


def _markup_vals(record, markup):
    """Values storing `markup` and its converted HTML, or {} when nothing changes."""
    current = (markup_lib.to_source(record.backup_text) or "").strip()
    new = markup.strip()
    if new == current and (record.is_finalized or not new):
        return {}
    if not new:
        return {"backup_text": False, "content_only_kanji": False, "content": False, "is_finalized": False}
    return record._apply_furigana({}, markup)


def create_comprehensive(env, body):
    vals, markup = _comprehensive_vals(env, body, creating=True)
    if markup:
        vals["content_only_kanji"] = markup  # converted by the furigana mixin on create
    item = env[COMPREHENSIVE].create(vals)
    after = get_comprehensive(env, item.id)
    audit(env, "comprehensive", item.id, "create", after=after)
    return after


def update_comprehensive(env, item_id, body, if_match):
    item = _get(env, COMPREHENSIVE, item_id, "Comprehensive")
    before = get_comprehensive(env, item_id)
    check_version(before["version"], if_match)
    vals, markup = _comprehensive_vals(env, body, creating=False)
    if markup is not None:
        vals.update(_markup_vals(item, markup))
    if vals:
        item.with_context(lj_furigana_processed=True).write(vals)
    after = get_comprehensive(env, item_id)
    if after["version"] != before["version"]:
        audit(env, "comprehensive", item.id, "update", before, after)
    return after


def delete_comprehensive(env, item_id, if_match):
    item = _get(env, COMPREHENSIVE, item_id, "Comprehensive")
    before = get_comprehensive(env, item_id)
    check_version(before["version"], if_match)
    item.unlink()
    audit(env, "comprehensive", item_id, "delete", before=before)


def audio_stream(env, item_id):
    item = _get(env, COMPREHENSIVE, item_id, "Comprehensive")
    if not item.audio_file:
        raise ApiError(404, "not-found", f"Comprehensive {item_id} has no audio.")
    return env["ir.binary"]._get_stream_from(item, "audio_file")


def put_audio(env, item_id, data, content_type, filename, if_match):
    item = _get(env, COMPREHENSIVE, item_id, "Comprehensive")
    before = get_comprehensive(env, item_id)
    check_version(before["version"], if_match, required=False)
    mimetype = (content_type or "").split(";")[0].strip().lower()
    if not mimetype.startswith("audio/"):
        raise ApiError(415, "unsupported-media-type", "Send the file with an audio/* Content-Type.")
    if not data:
        raise invalid([{"field": "body", "message": "The file is empty."}])
    if len(data) > AUDIO_MAX_BYTES:
        raise ApiError(413, "too-large", f"Audio files are limited to {AUDIO_MAX_BYTES} bytes.")
    item.write({"audio_file": base64.b64encode(data)})
    attachment = env["ir.attachment"].sudo().search(
        [("res_model", "=", COMPREHENSIVE), ("res_field", "=", "audio_file"), ("res_id", "=", item.id)], limit=1,
    )
    name = os.path.basename((filename or "").replace("\\", "/")).strip()[:200]
    attachment.write({"name": name or "audio_file", "mimetype": mimetype})
    after = get_comprehensive(env, item_id)
    audit(env, "comprehensive", item.id, "audio", {"audio": before["audio"]}, {"audio": after["audio"]})
    return after


def get_overrides(env, item_id):
    item = get_comprehensive(env, item_id)
    return {"items": item["grammar_overrides"], "version": item["version"]}


def put_overrides(env, item_id, body, if_match):
    item = _get(env, COMPREHENSIVE, item_id, "Comprehensive")
    before = get_comprehensive(env, item_id)
    check_version(before["version"], if_match, required=False)
    entries = body.get("items") if isinstance(body, dict) else None
    if not isinstance(entries, list):
        raise bad_request('The body must be {"items": [...]}.')
    if len(entries) > OVERRIDES_MAX:
        raise invalid([{"field": "items", "message": f"At most {OVERRIDES_MAX} entries."}])

    errors, values, seen = [], [], set()
    grammar_ids = [e.get("grammar_id") for e in entries if isinstance(e, dict) and _int_list([e.get("grammar_id")])]
    grammars = {g.id: g for g in env[COMPREHENSIVE].browse(grammar_ids).exists()}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append({"index": index, "message": "Each entry is an object."})
            continue
        grammar = grammars.get(entry.get("grammar_id"))
        if not grammar or not grammar.is_grammar:
            errors.append({"index": index, "field": "grammar_id", "message": "Not a comprehensive tagged Grammar."})
        elif grammar.id in seen:
            errors.append({"index": index, "field": "grammar_id", "message": "Listed twice."})
        if entry.get("action") not in ("pin", "hide"):
            errors.append({"index": index, "field": "action", "message": "pin or hide."})
        note = entry.get("note")
        if note is not None and (not isinstance(note, str) or len(note) > 500):
            errors.append({"index": index, "field": "note", "message": "A string of at most 500 characters."})
        if grammar:
            seen.add(grammar.id)
            values.append({"comprehensive_id": item.id, "grammar_id": grammar.id,
                           "action": entry.get("action"), "note": note or False})
    if errors:
        raise invalid(errors)

    item.grammar_override_ids.unlink()
    env["learning_japanese.grammar_override"].create(values)
    after = get_comprehensive(env, item_id)
    audit(env, "comprehensive", item.id, "grammar_overrides",
          {"grammar_overrides": before["grammar_overrides"]}, {"grammar_overrides": after["grammar_overrides"]})
    return {"items": after["grammar_overrides"], "version": after["version"]}


# ── Vocabularies ───────────────────────────────────────────────────────────────

_VOCABULARY_TEXT = {
    "hiragana": "higarana",
    "katakana": "katakana",
    "romaji": "romanji",
    "meaning_vi": "vietnamese",
    "han_viet": "han_viet",
}
_VOCABULARY_RELATIONS = {
    "part_of_speech_ids": "learning_japanese.part_of_speech",
    "context_tag_ids": "learning_japanese.context_tag",
    "lesson_ids": LESSON,
}
_VOCABULARY_KEYS = {
    "term", "level", "is_intransitive", "verb_group", "honorific_type", "forms", "examples_markup",
    *_VOCABULARY_TEXT, *_VOCABULARY_RELATIONS,
}


def vocabulary_domain(env, params):
    domain = level_domain(parse_levels(params))
    if ids := parse_ids(params):
        domain.append(("id", "in", ids))
    if q := (params.get("q") or "").strip():
        domain += ["|", "|", ("vocabulary", "ilike", q), ("higarana", "ilike", q), ("vietnamese", "ilike", q)]
    for name, field in (("book_id", "book_ids"), ("lesson_id", "lesson_ids"), ("context_tag_id", "context_tag_ids")):
        if (value := parse_int(params, name)) is not None:
            domain.append((field, "in", [value]))
    if (published := parse_bool(params, "published")) is not None:
        domain.append(("nihongo_published", "=", published))
    if updated_after := parse_datetime(params, "updated_after"):
        domain.append(("write_date", ">", updated_after))
    return domain


def list_vocabularies(env, params):
    records, next_cursor = paginate(env[VOCABULARY], vocabulary_domain(env, params), params)
    return {"items": [serializers.vocabulary(record) for record in records], "next_cursor": next_cursor}


def get_vocabulary(env, vocabulary_id):
    return serializers.vocabulary(_get(env, VOCABULARY, vocabulary_id, "Vocabulary"))


def _vocabulary_vals(env, body, creating):
    if not isinstance(body, dict):
        raise bad_request("The body must be a JSON object.")
    if not creating and not body:
        raise bad_request("Nothing to update.")
    errors = [{"field": key, "message": "Unknown field."} for key in sorted(set(body) - _VOCABULARY_KEYS)]
    vals = {}

    if "term" in body:
        term = body["term"]
        if not isinstance(term, str) or not term.strip() or len(term) > 200:
            errors.append({"field": "term", "message": "A non-empty string of at most 200 characters."})
        else:
            vals["vocabulary"] = term.strip()
    elif creating:
        errors.append({"field": "term", "message": "Required."})

    for key, field in _VOCABULARY_TEXT.items():
        if key in body:
            value = body[key]
            if value is not None and (not isinstance(value, str) or len(value) > 500):
                errors.append({"field": key, "message": "A string of at most 500 characters, or null."})
            else:
                vals[field] = (value or "").strip() or False

    if "level" in body:
        if body["level"] is not None and body["level"] not in serializers.LEVELS:
            errors.append({"field": "level", "message": "One of N5, N4, N3, N2, N1 or null."})
        else:
            vals["level"] = body["level"] or False

    if "is_intransitive" in body:
        if not isinstance(body["is_intransitive"], bool):
            errors.append({"field": "is_intransitive", "message": "true or false."})
        else:
            vals["is_intransitive"] = body["is_intransitive"]

    for key, field, mapping in (
        ("verb_group", "nhom_dong_tu", serializers.VERB_GROUPS),
        ("honorific_type", "nhom_ngu", serializers.HONORIFIC_TYPES),
    ):
        if key in body:
            reverse = {api: odoo for odoo, api in mapping.items()}
            if body[key] is not None and body[key] not in reverse:
                errors.append({"field": key, "message": f"One of {sorted(reverse)} or null."})
            else:
                vals[field] = reverse.get(body[key], False)

    if "forms" in body:
        forms = body["forms"]
        if not isinstance(forms, dict):
            errors.append({"field": "forms", "message": "An object of verb forms."})
        else:
            for name, value in forms.items():
                if name not in serializers.VERB_FORM_FIELDS:
                    errors.append({"field": f"forms.{name}", "message": "Unknown form."})
                elif value is not None and (not isinstance(value, str) or len(value) > 200):
                    errors.append({"field": f"forms.{name}", "message": "A string or null."})
                else:
                    vals[serializers.VERB_FORM_FIELDS[name]] = (value or "").strip() or False

    for key, model in _VOCABULARY_RELATIONS.items():
        if key in body:
            ids = body[key]
            if not _int_list(ids):
                errors.append({"field": key, "message": "A list of ids."})
                continue
            missing = set(ids) - set(env[model].browse(ids).exists().ids)
            if missing:
                errors.append({"field": key, "message": f"Unknown ids {sorted(missing)}."})
            else:
                vals[key] = [Command.set(ids)]

    markup = _markup_arg(body, "examples_markup", errors)
    if errors:
        raise invalid(errors)
    return vals, markup


def _check_unique_term(env, record, vals, index=None):
    """Same rule as the UNIQUE(vocabulary, vietnamese) constraint, checked first for a clean 409."""
    term = vals.get("vocabulary", record.vocabulary if record else False)
    meaning = vals.get("vietnamese", record.vietnamese if record else False)
    if not term or not meaning:
        return  # NULLs never collide in a unique constraint
    domain = [("vocabulary", "=", term), ("vietnamese", "=", meaning)]
    if record:
        domain.append(("id", "!=", record.id))
    if env[VOCABULARY].search_count(domain, limit=1):
        raise _unique_violation(index)


def _save_vocabulary(env, record, vals, markup, index=None):
    """Create (record is None) or update; returns the record."""
    _check_unique_term(env, record, vals, index)
    if record is None:
        if markup:
            vals["content_only_kanji"] = markup
        return env[VOCABULARY].create(vals)
    if markup is not None:
        vals.update(_markup_vals(record, markup))
    if vals:
        record.with_context(lj_furigana_processed=True).write(vals)
    return record


def _unique_violation(index=None):
    entry = {"field": "term", "message": "Another entry has the same term and meaning_vi."}
    if index is not None:
        entry["index"] = index
    return ApiError(409, "conflict", "Vocabulary term and meaning must be unique together.", errors=[entry])


def create_vocabulary(env, body):
    vals, markup = _vocabulary_vals(env, body, creating=True)
    try:
        with env.cr.savepoint():
            record = _save_vocabulary(env, None, vals, markup)
    except psycopg2.errors.UniqueViolation:
        raise _unique_violation() from None
    after = serializers.vocabulary(record)
    audit(env, "vocabulary", record.id, "create", after=after)
    return after


def update_vocabulary(env, vocabulary_id, body, if_match):
    record = _get(env, VOCABULARY, vocabulary_id, "Vocabulary")
    before = serializers.vocabulary(record)
    check_version(before["version"], if_match)
    vals, markup = _vocabulary_vals(env, body, creating=False)
    try:
        with env.cr.savepoint():
            _save_vocabulary(env, record, vals, markup)
    except psycopg2.errors.UniqueViolation:
        raise _unique_violation() from None
    after = serializers.vocabulary(record)
    if after["version"] != before["version"]:
        audit(env, "vocabulary", record.id, "update", before, after)
    return after


def delete_vocabulary(env, vocabulary_id, if_match):
    record = _get(env, VOCABULARY, vocabulary_id, "Vocabulary")
    before = serializers.vocabulary(record)
    check_version(before["version"], if_match)
    record.unlink()
    audit(env, "vocabulary", vocabulary_id, "delete", before=before)


def bulk_vocabularies(env, body):
    """All entries or none: the controller's savepoint rolls back on any error."""
    entries = body.get("items") if isinstance(body, dict) else None
    if not isinstance(entries, list) or not entries:
        raise bad_request('The body must be {"items": [...]} with at least one entry.')
    if len(entries) > BULK_MAX:
        raise invalid([{"field": "items", "message": f"At most {BULK_MAX} entries."}])

    prepared, errors = [], []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append({"index": index, "message": "Each entry is an object."})
            continue
        fields_ = {k: v for k, v in entry.items() if k not in ("id", "version")}
        record_id = entry.get("id")
        if record_id is not None and not _int_list([record_id]):
            errors.append({"index": index, "field": "id", "message": "A positive integer."})
            continue
        try:
            vals, markup = _vocabulary_vals(env, fields_, creating=record_id is None)
        except ApiError as error:
            errors += [{"index": index, **e} for e in (error.errors or [{"message": error.detail}])]
            continue
        prepared.append((index, record_id, entry.get("version"), vals, markup))
    if errors:
        raise invalid(errors)

    results = []
    for index, record_id, version, vals, markup in prepared:
        record = None
        if record_id is not None:
            record = env[VOCABULARY].browse(record_id).exists()
            if not record:
                raise ApiError(404, "not-found", f"Vocabulary {record_id} does not exist.",
                               errors=[{"index": index, "field": "id", "message": "Not found."}])
            before = serializers.vocabulary(record)
            if version and before["version"] != str(version).strip('"'):
                raise ApiError(412, "version-mismatch", f"Entry {index} changed since you read it.",
                               errors=[{"index": index, "field": "version", "message": "Stale version."}],
                               current_version=before["version"])
        try:
            with env.cr.savepoint():
                saved = _save_vocabulary(env, record, vals, markup, index)
        except psycopg2.errors.UniqueViolation:
            raise _unique_violation(index) from None
        after = serializers.vocabulary(saved)
        audit(env, "vocabulary", saved.id, "update" if record else "create", before if record else None, after)
        results.append(after)
    return {"items": results}
