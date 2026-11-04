"""apply_topic.py OUT.json [--apply]: write one converted topic of the 2400 book to Odoo (API v1), then read it back.

Without --apply nothing is written: the markups go through /markup/preview and Odoo's HTML sanitizer, the words
that already exist are compared with what would replace them, and the plan is printed.
With --apply: the words (bulk, 100 at a time, all or nothing per call), then the item of the topic; the ids are kept
in DATA/applied/topicNN.json; then everything is read back and compared field by field.

Until the addon has meaning_en / meaning_zh (commit 166bcc1a, not yet deployed), the English and Chinese meanings
of a word wait at the top of its examples, as `<p>{{en: …}}<br>{{zh: …}}</p>` (NihonGo drops both, ADR-052);
move_meanings.py moves them into the fields once the addon is deployed.

Run: env -u LJ_API_KEY uv run --project ../lj-readings python apply_topic.py OUT.json [--apply]
"""

import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lj-readings"))
from fetch import client, read_all
from odoo_html import read_back, to_send

DATA = Path(os.environ.get("LJ_2400_DATA") or Path(__file__).resolve().parent / "data")
REPO = Path(__file__).resolve().parents[2]
BLOCKING = {
    "unbalanced_marker",
    "empty_marker",
    "reading_not_kana",
    "unbalanced_translation",
    "kanji_without_reading",
    "auto_reading",
    "untagged_translation",
    "missing_translation",
}
FIELDS = (
    "term",
    "hiragana",
    "katakana",
    "romaji",
    "meaning_vi",
    "meaning_en",
    "meaning_zh",
    "han_viet",
    "level",
    "part_of_speech_ids",
    "lesson_ids",
    "verb_group",
    "is_intransitive",
    "forms",
    "examples_markup",
)


def check_markup(api, markup, where, problems):
    if read_back(markup) != markup:
        problems.append(f"{where}: Odoo's sanitizer would change the markup")
    preview = api.post("/markup/preview", json={"markup": markup}).raise_for_status().json()
    for issue in preview["issues"]:
        if issue["code"] in BLOCKING:
            problems.append(f"{where}: {issue['code']} {issue.get('text', '')}".rstrip())
    return preview["stats"]


INTERIM = False  # set in main(): the addon has no meaning_en / meaning_zh yet


def fields():
    return tuple(k for k in FIELDS if not (INTERIM and k in ("meaning_en", "meaning_zh")))


def examples_of(word):
    """The examples as they are stored: with the English and Chinese meanings on top while INTERIM."""
    if not INTERIM:
        return word["examples_markup"]
    lines = [
        f"{{{{{lang}: {html.escape(word[f'meaning_{lang}'], quote=False)}}}}}"
        for lang in ("en", "zh")
        if word.get(f"meaning_{lang}")
    ]
    return (f"<p>{'<br>'.join(lines)}</p>" if lines else "") + word["examples_markup"]


def body_of(word):
    body = {key: word[key] for key in fields()}
    body["examples_markup"] = to_send(examples_of(word))
    if word["match"]:
        body["id"] = word["match"]
    return body


def differs(saved, word):
    out = []
    for key in fields():
        want = examples_of(word) if key == "examples_markup" else word[key]
        have = saved.get(key)
        if key == "examples_markup":
            want = read_back(want)
        if key in ("part_of_speech_ids", "lesson_ids"):
            want, have = sorted(want), sorted(have or [])
        if key == "forms":
            have = {name: value for name, value in (have or {}).items()}
        if have != want:
            out.append(key)
    return out


def main():
    out = json.loads(Path(sys.argv[1]).read_text())
    write = "--apply" in sys.argv
    api = client()
    topic = out["topic"]
    problems = list(out["report"])

    global INTERIM
    probe = api.get("/vocabularies", params={"limit": 1}).raise_for_status().json()["items"]
    INTERIM = bool(probe) and "meaning_en" not in probe[0]
    if INTERIM:
        print("Odoo has no meaning_en yet: English and Chinese meanings go on top of the examples for now")

    item = out["item"]
    stats = check_markup(api, item["markup"], f"item of topic {topic}", problems)
    print(
        f"item: {item['title']}, {stats['blocks']} blocks, {stats['explicit_readings']} readings, "
        f"{stats['translations']} translations"
    )
    for markup in dict.fromkeys(w["examples_markup"] for w in out["words"]):
        check_markup(api, markup, f"examples of {markup[:12]}", problems)
    for word in out["words"][:3]:
        check_markup(api, examples_of(word), f"examples of word {word['no']}", problems)

    words = out["words"]
    changes = []
    for word in words:
        if word["match"]:
            current = api.get(f"/vocabularies/{word['match']}").raise_for_status().json()
            fields = [k for k in differs(current, word) if k != "examples_markup"]
            changes.append(
                f"  #{word['match']} → book {word['no']}: "
                + ", ".join(f"{k}: {current.get(k)!r} → {word[k]!r}" for k in fields)
            )
    creates = sum(1 for w in words if not w["match"])
    print(f"words: {creates} to create, {len(words) - creates} to update")
    print("\n".join(changes))
    if problems:
        print("PROBLEMS:")
        print("\n".join(f"  - {p}" for p in problems))
    if not write:
        print("dry run: nothing written")
        return
    if problems:
        sys.exit("not written: fix the problems first")

    applied_path = DATA / "applied" / f"topic{topic:02d}.json"
    applied_path.parent.mkdir(exist_ok=True)
    applied = json.loads(applied_path.read_text()) if applied_path.exists() else {"words": {}}
    for start in range(0, len(words), 100):
        chunk = words[start : start + 100]
        items = [body_of({**w, "match": w["match"] or applied["words"].get(str(w["no"]))}) for w in chunk]
        response = api.post("/vocabularies/bulk", json={"items": items})
        if not response.is_success:
            sys.exit(f"bulk {start}: {response.status_code} {response.text[:2000]}")
        for word, saved in zip(chunk, response.json()["items"], strict=True):
            applied["words"][str(word["no"])] = saved["id"]
        applied_path.write_text(json.dumps(applied, ensure_ascii=False, indent=1))
        print(f"words {start + 1}–{start + len(chunk)} saved")

    body = {key: item[key] for key in ("title", "level", "tags", "lesson_ids")}
    body["markup"] = to_send(item["markup"])
    item_id = item["id"] or applied.get("item")
    if item_id:
        current = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        response = api.patch(f"/comprehensives/{item_id}", json=body, headers={"If-Match": f'"{current["version"]}"'})
    else:
        response = api.post("/comprehensives", json=body)
    if not response.is_success:
        sys.exit(f"item: {response.status_code} {response.text[:2000]}")
    applied["item"] = response.json()["id"]
    applied_path.write_text(json.dumps(applied, ensure_ascii=False, indent=1))
    print(f"item #{applied['item']} saved")

    # read everything back
    saved_item = api.get(f"/comprehensives/{applied['item']}").raise_for_status().json()
    bad = []
    if saved_item["markup"] != read_back(item["markup"]):
        bad.append(f"item #{applied['item']}: markup differs")
    for key in ("title", "level"):
        if saved_item[key] != item[key]:
            bad.append(f"item #{applied['item']}: {key} {saved_item[key]!r}")
    by_id = {w["id"]: w for w in read_all(api, "/vocabularies", {"lesson_id": item["lesson_ids"][0]})}
    for word in words:
        word_id = applied["words"][str(word["no"])]
        saved = by_id.get(word_id)
        if saved is None:
            bad.append(f"word {word['no']} #{word_id}: not in the lesson")
            continue
        fields = differs(saved, word)
        if fields:
            bad.append(f"word {word['no']} #{word_id}: {', '.join(fields)} differ")
    extra = set(by_id) - set(applied["words"].values())
    if extra:
        bad.append(f"lesson has other words too: {sorted(extra)}")
    print("read back: " + ("everything as sent" if not bad else f"{len(bad)} differences"))
    print("\n".join(f"  - {b}" for b in bad))


if __name__ == "__main__":
    main()
