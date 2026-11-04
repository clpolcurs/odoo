"""report_fixes.py OUT.md: every change of fixes.json, next to the book's text, for the author's review (Vietnamese).

For each word: the book's text and what was written instead; a Vietnamese meaning that only differs because the book's
one is already taken by a word of another book (UNIQUE(vocabulary, vietnamese)) is listed apart, with that word.
For each part: the translation fixes. Reads DATA/raw/topicNN.json, DATA/out/topicNN.json and DATA/vocab_all.json.

Run: LJ_2400_DATA=… python3 -I report_fixes.py OUT.md
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("LJ_2400_DATA", HERE / "data"))
BOOK_LESSONS = set(range(1646, 1669))
FIELDS = {
    "vi": "nghĩa tiếng Việt",
    "en": "nghĩa tiếng Anh",
    "zh": "nghĩa tiếng Trung",
    "tags": "nhãn loại từ",
    "term": "cách viết",
    "ruby": "furigana",
    "match": "ghép với từ có sẵn",
}
LANGS = {"vi": "tiếng Việt", "en": "tiếng Anh", "zh": "tiếng Trung"}


def cell(value):
    text = " ".join(value) if isinstance(value, list) else str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")


def main():
    fixes = json.loads((HERE / "fixes.json").read_text())
    raw_words, raw_parts, out_words, topic_of = {}, {}, {}, {}
    for path in sorted((DATA / "raw").glob("topic[0-9][0-9].json")):
        raw = json.loads(path.read_text())
        for part in raw["parts"]:
            raw_parts[part["part"]] = part
            topic_of[f"p{part['part']}"] = raw["topic"]
            for word in part["words"]:
                raw_words[word["no"]] = word
                topic_of[str(word["no"])] = raw["topic"]
        out_path = DATA / "out" / path.name
        if out_path.exists():
            out_words.update({w["no"]: w for w in json.loads(out_path.read_text())["words"]})
    others = {}
    for word in json.loads((DATA / "vocab_all.json").read_text()):
        if not BOOK_LESSONS & set(word.get("lesson_ids") or []):
            others.setdefault((word["term"], word.get("meaning_vi")), word["id"])
    book_vi = {}
    for no, word in raw_words.items():
        if no in out_words:
            book_vi.setdefault((out_words[no]["term"], word.get("vi")), []).append(no)

    errors, duplicates, parts = [], [], []
    for key, fix in fixes.items():
        if key.startswith("p"):
            for lang, pairs in fix.items():
                for old, new in pairs:
                    parts.append((topic_of.get(key, 0), int(key[1:]), LANGS.get(lang, lang), old, new))
            continue
        no = int(key)
        word = raw_words.get(no, {})
        term = out_words.get(no, {}).get("term", word.get("term", ""))
        for field, new in fix.items():
            old = word.get(field)
            row = (topic_of.get(key, 0), no, term, FIELDS.get(field, field), old, new)
            if field == "vi" and len(fix) == 1:
                other = others.get((term, old))
                twins = [n for n in book_vi.get((term, old), []) if n != no]
                if other or twins:
                    where = f"#{other} (sách khác)" if other else f"từ {twins[0]} của sách này"
                    duplicates.append((*row, where))
                    continue
            errors.append(row)

    lines = [
        "# Các chỗ đã sửa khi nhập sách 2400",
        "",
        f"{len(errors)} chỗ sửa ở từ vựng, {len(parts)} chỗ sửa ở bản dịch, "
        f"{len(duplicates)} nghĩa tiếng Việt viết đầy đủ hơn vì trùng với từ đã có.",
        "",
    ]
    lines += ["## Từ vựng", "", "| Topic | Số | Từ | Trường | Sách | Đã ghi |", "| --- | --- | --- | --- | --- | --- |"]
    lines += [
        f"| {t} | {no} | {cell(term)} | {f} | {cell(old)} | {cell(new)} |"
        for t, no, term, f, old, new in sorted(errors, key=lambda r: r[1])
    ]
    lines += [
        "",
        "## Bản dịch của các phần",
        "",
        "| Topic | Phần | Ngôn ngữ | Sách | Đã ghi |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [f"| {t} | {p} | {lang} | {cell(old)} | {cell(new)} |" for t, p, lang, old, new in sorted(parts)]
    lines += [
        "",
        "## Nghĩa tiếng Việt viết đầy đủ hơn vì trùng",
        "",
        "Odoo không cho hai từ trùng cả chữ lẫn nghĩa tiếng Việt, nên các từ này có nghĩa dài hơn sách.",
        "",
        "| Topic | Số | Từ | Sách | Đã ghi | Trùng với |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {t} | {no} | {cell(term)} | {cell(old)} | {cell(new)} | {where} |"
        for t, no, term, _, old, new, where in sorted(duplicates, key=lambda r: r[1])
    ]
    Path(sys.argv[1]).write_text("\n".join(lines) + "\n")
    print(f"{len(errors)} word fixes, {len(parts)} translation fixes, {len(duplicates)} duplicates -> {sys.argv[1]}")


if __name__ == "__main__":
    main()
