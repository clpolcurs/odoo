"""Write hand-made brace edits to Odoo, one PATCH per item: the translations the rules leave to a person (too short
to tell, in a table cell, cut by a formatting tag) and braces that should hold a whole line.

usage: python apply_edits.py proposals/translations/<file>.json            check against Odoo, write nothing
       python apply_edits.py proposals/translations/<file>.json --apply    write (If-Match: the version read now)

  {"<item id>": {"note": "why", "edits": [["old fragment", "new fragment"], ...]}}

Each old fragment must occur exactly once in the markup, and its new fragment must be the same markup with braces
added, taken off or moved. Before writing, the new markup must have as many translations more in /markup/preview as
brace pairs added less pairs taken off, no more untagged translations than before, no new markup problem, and come
back unchanged through Odoo's HTML sanitizer (odoo_html.py). Only run --apply on edits the content owner approved.
"""

import json
import sys
from pathlib import Path

from apply_translations import PROBLEMS
from fetch import client
from odoo_html import read_back, to_send


def without_braces(markup):
    return markup.replace("{{", "").replace("}}", "")


def edited(markup, edits):
    """The markup with the edits made, and the brace pairs they add (less those they take off); or why not."""
    pairs = 0
    for old, new in edits:
        if without_braces(old) != without_braces(new):
            return None, 0, f"more than braces would change: {old[:40]!r}"
        found = markup.count(old)
        if found != 1:
            return None, 0, f"found {found} times instead of once: {old[:40]!r}"
        markup = markup.replace(old, new)
        pairs += new.count("{{") - old.count("{{")
    return markup, pairs, None


def problem_of(old, new, before, after, pairs):
    """Why the edited markup must not be written, or None."""
    if without_braces(new) != without_braces(old):
        return "more than braces would change"
    added = after["stats"]["translations"] - before["stats"]["translations"]
    if added != pairs:
        return f"{added} translations more instead of {pairs}"
    untagged = "untagged_translations"
    if untagged in before["stats"] and after["stats"][untagged] > before["stats"][untagged]:
        return f"{after['stats'][untagged] - before['stats'][untagged]} untagged translations more"
    for code in PROBLEMS:
        if sum(i["code"] == code for i in after["issues"]) > sum(i["code"] == code for i in before["issues"]):
            return f"new {code} issue"
    if read_back(new) != new:
        return "Odoo's HTML sanitizer would store a different markup"
    return None


def main():
    edits = json.loads(Path(sys.argv[1]).read_text())
    write = "--apply" in sys.argv
    api = client()
    ready, skipped, total = 0, [], 0
    for item_id, entry in edits.items():
        item = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        old = item["markup"] or ""
        new, pairs, why = edited(old, entry["edits"])
        if why is None:
            before = api.post("/markup/preview", json={"markup": old}).raise_for_status().json()
            after = api.post("/markup/preview", json={"markup": new}).raise_for_status().json()
            why = problem_of(old, new, before, after, pairs)
        if why:
            skipped.append(f"#{item_id}: {why}")
            continue
        ready += 1
        total += len(entry["edits"])
        if not write:
            continue
        response = api.patch(
            f"/comprehensives/{item_id}", json={"markup": to_send(new)}, headers={"If-Match": f'"{item["version"]}"'}
        )
        if not response.is_success:
            skipped.append(f"#{item_id}: FAILED {response.status_code} {response.text[:200]}")
            ready -= 1
            total -= len(entry["edits"])
            continue
        saved = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        status = "saved" if saved["markup"] == new else "saved, but the markup read back differs"
        print(f"#{item_id}: {status} ({len(entry['edits'])} edits, {pairs:+d} translations)")
    for line in skipped:
        print(line)
    print(f"{ready} of {len(edits)} items {'written' if write else 'ready to write (dry run)'} with {total} edits, "
          f"{len(skipped)} skipped")  # fmt: skip


if __name__ == "__main__":
    main()
