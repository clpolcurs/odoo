"""Change feed and snapshots used by NihonGo to stay in sync."""

from . import serializers
from .content_service import (
    BOOK,
    COMPREHENSIVE,
    LESSON,
    TAG,
    VOCABULARY,
    paginate,
    parse_bool,
    parse_csv,
    parse_limit,
    tag_ids,
)
from .errors import ApiError, bad_request, not_found

CHANGES_DEFAULT, CHANGES_MAX = 500, 1000
SNAPSHOT_MAX = 1000

# entity -> (model, serializer, domain keeping only what a published book contains)
SNAPSHOTS = {
    "comprehensives": (COMPREHENSIVE, serializers.comprehensives, [("nihongo_published", "=", True)]),
    "vocabularies": (VOCABULARY, lambda records: [serializers.vocabulary(r) for r in records],
                     [("nihongo_published", "=", True)]),
    "books": (BOOK, serializers.books, [("nihongo_published", "=", True)]),
    "lessons": (LESSON, serializers.lessons, [("book_id.nihongo_published", "=", True)]),
    "tags": (TAG, lambda records: [serializers.tag(r) for r in records], None),
    "context-tags": ("learning_japanese.context_tag", lambda records: [serializers.context_tag(r) for r in records], None),
    "parts-of-speech": ("learning_japanese.part_of_speech",
                        lambda records: [serializers.part_of_speech(r) for r in records], None),
    "hanviet": ("learning_japanese.hanviet", lambda records: [serializers.hanviet(r) for r in records], None),
}


def changes(env, params):
    limit = parse_limit(params, CHANGES_DEFAULT, CHANGES_MAX)
    try:
        events, next_after, has_more = env["learning_japanese.change_log"]._read_after(params.get("after"), limit)
    except ValueError:
        raise bad_request("Invalid cursor in after.") from None
    except LookupError:
        raise ApiError(410, "cursor-expired",
                       "Events after this cursor were purged; take a snapshot and continue from its feed_cursor.") from None
    for event in events:
        event["at"] = serializers.iso(event["at"])
    return {"events": events, "next_after": next_after, "has_more": has_more}


def head(env):
    return {"cursor": env["learning_japanese.change_log"]._head_cursor()}


def snapshot(env, entity, params):
    if entity not in SNAPSHOTS:
        raise not_found("Snapshot entity", entity)
    model, serialize, published_domain = SNAPSHOTS[entity]
    published_only = parse_bool(params, "published_only")
    domain = list(published_domain or []) if published_only is not False else []
    if names := parse_csv(params, "tag"):
        if entity != "comprehensives":
            raise bad_request("tag only filters comprehensives.")
        domain.append(("category_ids", "in", tag_ids(env, names)))

    # Same transaction snapshot as the data below: events after this cursor are not in the data.
    feed_cursor = None if params.get("cursor") else head(env)["cursor"]
    records, next_cursor = paginate(env[model], domain, params, SNAPSHOT_MAX, SNAPSHOT_MAX)
    page = {"items": [{"id": data["id"], "version": data["version"]} for data in serialize(records)],
            "next_cursor": next_cursor}
    if feed_cursor:
        page["feed_cursor"] = feed_cursor
    return page
