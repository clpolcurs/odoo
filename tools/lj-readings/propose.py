"""Write the reading proposals of each book from data/items.json (fetch.py).

usage: python propose.py [--auto] [book id ...]     every book with published items when no id is given

  proposals/<book>.json         {"<item id>": {"version": "...", "markers": [[start, end, text, reading], ...],
                                               "fixes": [[start, end, text, replacement], ...]}}  (fixes: typos)
                                what apply.py writes, pinned to the version of the item it was made from
  proposals/<book>_report.json  the same grouped by kanji and reading, with examples, for the review

--auto proposes readings for the markers written without one instead (proposals/auto/): their kanji are marked
again inside them and their brackets go (fixes); the report lists the markers kept as they are, the markers with no
kanji, and the full reading of every marker replaced.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from readings import BRACKETS, RE_KANJI, RE_MARKER, RE_READING, Proposer, apply, known_readings

HERE = Path(__file__).parent
SLUGS = {
    158: "minna-1", 159: "minna-2", 162: "try-n2", 163: "try-n3", 166: "drill-n2-moji-goi", 167: "drill-n2-bunpo",
    168: "drill-n2-choukai-dokkai", 175: "mimi-bunpo-n2",
}  # fmt: skip
# items whose markup must be fixed by hand before any reading is added
BY_HAND = {}  # {item id: why}; #244 (doubled characters) was rewritten by hand on 27/10


def file_name(book):
    slug = SLUGS.get(book["id"]) or re.sub(r"[^a-z0-9]+", "-", book["name"].lower()).strip("-") or "book"
    return f"{book['id']}-{slug}"


def start_of(marker):
    return marker.start


def kind_of(marker):
    if marker.doubt:
        return "doubt"
    if marker.note == "số đếm":
        return "number"
    return "content" if marker.note else "plain"


def full_readings(markup, proposal, item_id):
    """{item, text, reading} of each marker without reading the proposal replaces: reading is its whole word read,
    or None when a new marker also takes in text beside it (the number of 22<<歳>>)."""
    fixed, out = apply(markup, [], proposal.fixes), []
    for start, end, text in proposal.replaced:
        covering = sorted((m for m in proposal.markers if m.start < end and m.end > start), key=start_of)
        if any(m.start < start or m.end > end for m in covering):
            out.append({"item": item_id, "text": text, "reading": None})
            continue
        reading, at = "", start
        for m in covering:
            reading, at = reading + fixed[at : m.start] + m.reading, m.end
        out.append({"item": item_id, "text": text, "reading": reading + fixed[at:end]})
    return out


def main():
    items = json.loads((HERE / "data" / "items.json").read_text())
    books = {b["id"]: b for b in json.loads((HERE / "data" / "books.json").read_text())}
    proposer = Proposer(known_readings(item["markup"] for item in items))
    auto = "--auto" in sys.argv
    wanted = {int(a) for a in sys.argv[1:] if a != "--auto"}
    out_dir = HERE / "proposals" / ("auto" if auto else "")
    out_dir.mkdir(exist_ok=True)
    by_book = defaultdict(list)
    for item in items:
        if item["book_ids"]:
            by_book[item["book_ids"][0]].append(item)
    for book_id, book_items in sorted(by_book.items()):
        if wanted and book_id not in wanted:
            continue
        proposals, rows, missing, fixes, no_kanji, converted = {}, {}, [], [], {}, []
        for item in sorted(book_items, key=lambda i: i["id"]):
            if item["id"] in BY_HAND:
                missing.append(dict(item=item["id"], text="cả bài", why=BY_HAND[item["id"]], context=item["title"]))
                continue
            markup = item["markup"] or ""
            proposal = proposer.propose_auto(markup) if auto else proposer.propose(markup)
            if auto:
                for m in RE_MARKER.finditer(markup):
                    if not RE_KANJI.search(m.group(1)) and not RE_READING.match(m.group(1)):
                        no_kanji.setdefault(m.group(1).strip(), []).append(item["id"])
                converted += full_readings(markup, proposal, item["id"])
            missing += [dict(item=item["id"], text=m.text, why=m.why, context=m.context) for m in proposal.missing]
            if not proposal.markers and not proposal.fixes:
                continue
            proposals[str(item["id"])] = {
                "version": item["version"],
                "markers": [[m.start, m.end, m.text, m.reading] for m in sorted(proposal.markers, key=start_of)],
            }
            if proposal.fixes:
                proposals[str(item["id"])]["fixes"] = [[f.start, f.end, f.text, f.replacement] for f in proposal.fixes]
                fixes += [dict(item=item["id"], text=f.text, to=f.replacement, why=f.why, context=f.context)
                          for f in proposal.fixes if f.why != BRACKETS]  # fmt: skip
            for m in proposal.markers:
                key = (m.text, m.reading, m.doubt, m.note)
                row = rows.setdefault(key, {"text": m.text, "reading": m.reading, "kind": kind_of(m), "doubt": m.doubt,
                                            "note": m.note, "count": 0, "words": [], "examples": []})  # fmt: skip
                row["count"] += 1
                if m.word not in row["words"]:
                    row["words"].append(m.word)
                if len(row["examples"]) < (60 if m.doubt else 2):
                    row["examples"].append({"item": item["id"], "context": m.context})
        name = file_name(books.get(book_id, {"id": book_id, "name": str(book_id)}))
        (out_dir / f"{name}.json").write_text(json.dumps(proposals, ensure_ascii=False, indent=0) + "\n")
        order = {"doubt": 0, "content": 1, "number": 2, "plain": 3}
        report = {
            "book": {"id": book_id, "name": books.get(book_id, {}).get("name", "")},
            "items": len(book_items),
            "items_changed": len(proposals),
            "markers": sum(len(p["markers"]) for p in proposals.values()),
            "rows": sorted(rows.values(), key=lambda r: (order[r["kind"]], -r["count"], r["text"])),
            "missing": missing,
            "fixes": fixes,
        }
        if auto:
            report["no_kanji"] = sorted(([text, ids] for text, ids in no_kanji.items()), key=lambda r: -len(r[1]))
            report["converted"] = converted
        (out_dir / f"{name}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
        counts = defaultdict(int)
        for row in rows.values():
            counts[row["kind"]] += row["count"]
        print(f"{name}: {report['markers']} markers in {len(proposals)}/{len(book_items)} items, "
              f"{dict(counts)}, {len(missing)} kanji left for a person")  # fmt: skip


if __name__ == "__main__":
    main()
