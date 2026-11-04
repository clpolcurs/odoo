"""move_meanings.py [--apply]: once the addon has meaning_en / meaning_zh (commit 166bcc1a deployed), move the English
and Chinese meanings of the words of book 153 from the top of their examples into those fields.

apply_topic.py put them there while the fields did not exist: examples start with `<p>{{en: …}}<br>{{zh: …}}</p>`.
Everything is read from Odoo, so nothing of this session is needed. Without --apply it only prints what it would do.
NihonGo is not affected: it ignores both fields and drops {{en: …}} / {{zh: …}} from examples (ADR-052).

Run: env -u LJ_API_KEY uv run --project ../lj-readings python move_meanings.py [--apply]
"""

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lj-readings"))
from fetch import client, read_all
from odoo_html import read_back, to_send

BOOK = 153
HEAD = re.compile(r"^\s*<p>((?:\{\{\s*(?:en|zh)\s*:.*?\}\}(?:<br\s*/?>)?)+)</p>", re.DOTALL)
LINE = re.compile(r"\{\{\s*(en|zh)\s*:\s*(.*?)\}\}", re.DOTALL)


def split(examples):
    """(meanings {"en": …, "zh": …}, the examples without them), or (None, examples) when there is no such head."""
    match = HEAD.match(examples or "")
    if not match:
        return None, examples
    meanings = {lang: html.unescape(text).strip() for lang, text in LINE.findall(match.group(1))}
    return meanings, examples[match.end() :]


def main():
    write = "--apply" in sys.argv
    api = client()
    words = read_all(api, "/vocabularies", {"book_id": BOOK})
    if words and "meaning_en" not in words[0]:
        sys.exit("Odoo has no meaning_en yet: deploy the addon (commit 166bcc1a) first")
    todo = []
    for word in words:
        meanings, rest = split(word.get("examples_markup"))
        if meanings is None:
            continue
        body = {"id": word["id"], "version": word["version"], "examples_markup": to_send(rest)}
        for lang in ("en", "zh"):
            if lang in meanings:
                body[f"meaning_{lang}"] = meanings[lang]
        todo.append((word, body, rest))
    print(f"{len(todo)} of {len(words)} words of book {BOOK} have meanings to move")
    if not write:
        for word, body, _ in todo[:5]:
            print(f"  #{word['id']} {word['term']}: en={body.get('meaning_en')!r} zh={body.get('meaning_zh')!r}")
        print("dry run: nothing written")
        return
    for start in range(0, len(todo), 100):
        chunk = todo[start : start + 100]
        response = api.post("/vocabularies/bulk", json={"items": [body for _, body, _ in chunk]})
        if not response.is_success:
            sys.exit(f"bulk {start}: {response.status_code} {response.text[:2000]}")
        for (word, body, rest), saved in zip(chunk, response.json()["items"], strict=True):
            ok = (
                saved.get("meaning_en") == body.get("meaning_en")
                and saved.get("meaning_zh") == body.get("meaning_zh")
                and saved.get("examples_markup") == read_back(rest)
            )
            if not ok:
                print(f"  #{word['id']} {word['term']}: read back differs")
        print(f"words {start + 1}–{start + len(chunk)} moved")


if __name__ == "__main__":
    main()
