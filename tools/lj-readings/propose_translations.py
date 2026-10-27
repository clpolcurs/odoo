"""Write the {{...}} proposals of each book from data/items.json (fetch.py): QA issue untagged_translation.

usage: python propose_translations.py [book id ...]     every book with published items when no id is given

  proposals/translations/<book>.json         {"<item id>": {"version": "...", "wraps": [[start, end, text], ...],
                                             "unwraps": [[start, end, text], ...]}}: braces to add around
                                             translations and to take off explanations, what apply_translations.py
                                             writes, pinned to the version of the item
  proposals/translations/<book>_report.json  counts, examples of each rule, the translations left to a person
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from propose import file_name
from translations import explanations, find

HERE = Path(__file__).parent
EXAMPLES = 12


def main():
    items = json.loads((HERE / "data" / "items.json").read_text())
    books = {b["id"]: b for b in json.loads((HERE / "data" / "books.json").read_text())}
    wanted = {int(a) for a in sys.argv[1:]}
    out_dir = HERE / "proposals" / "translations"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_book = defaultdict(list)
    for item in items:
        if item["book_ids"]:
            by_book[item["book_ids"][0]].append(item)
    total = defaultdict(int)
    for book_id, book_items in sorted(by_book.items()):
        if wanted and book_id not in wanted:
            continue
        proposals, examples, doubts, rules, unwrapped = {}, defaultdict(list), [], defaultdict(int), []
        for item in sorted(book_items, key=lambda i: i["id"]):
            found = find(item["markup"] or "")
            unwraps = explanations(item["markup"] or "")
            doubts += [{"item": item["id"], "text": text, "why": why} for text, why in found.doubts]
            if not found.wraps and not unwraps:
                continue
            proposals[str(item["id"])] = {
                "version": item["version"],
                "wraps": [[w.start, w.end, w.text] for w in found.wraps],
            }
            if unwraps:
                proposals[str(item["id"])]["unwraps"] = [[u.start, u.end, u.text] for u in unwraps]
                unwrapped += [{"item": item["id"], "term": u.before, "explanation": u.text} for u in unwraps]
            for wrap in found.wraps:
                rules[wrap.rule] += 1
                examples[wrap.rule].append({"item": item["id"], "japanese": wrap.before, "translation": wrap.text})
        random.seed(book_id)  # the same examples on every run
        report = {
            "book": {"id": book_id, "name": books.get(book_id, {}).get("name", "")},
            "items": len(book_items),
            "items_changed": len(proposals),
            "wraps": sum(rules.values()),
            "rules": dict(rules),
            "examples": {rule: random.sample(rows, min(EXAMPLES, len(rows))) for rule, rows in examples.items()},
            "unwraps": unwrapped,
            "doubts": doubts,
        }
        name = file_name(books.get(book_id, {"id": book_id, "name": str(book_id)}))
        (out_dir / f"{name}.json").write_text(json.dumps(proposals, ensure_ascii=False, indent=0) + "\n")
        (out_dir / f"{name}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
        for key in ("items", "items_changed", "wraps"):
            total[key] += report[key]
        total["unwraps"] += len(unwrapped)
        total["doubts"] += len(doubts)
        print(f"{name}: {report['wraps']} translations in {len(proposals)}/{len(book_items)} items "
              f"{dict(rules)}, {len(unwrapped)} explanations to unwrap, {len(doubts)} left for a person")  # fmt: skip
    print(f"total: {dict(total)}")


if __name__ == "__main__":
    main()
