"""Write approved {{...}} proposals to Odoo, one PATCH per item.

usage: python apply_translations.py proposals/translations/<book>.json            check against Odoo, write nothing
       python apply_translations.py proposals/translations/<book>.json --apply    write (If-Match: the version the
                                                                                   proposal was made from)

An item edited after the proposal was made is skipped: run fetch.py and propose_translations.py again for it. Before
writing, the new markup must be the old one with only the braces added, have one translation more per brace pair in
/markup/preview and, where Odoo already reports the issue, one untagged translation less; no new markup problem; and
come back unchanged through Odoo's HTML sanitizer (odoo_html.py). Only run --apply on proposals the content owner
approved.
"""

import json
import sys
from pathlib import Path

from fetch import client
from odoo_html import read_back, to_send
from translations import Wrap, apply, find

PROBLEMS = ("unbalanced_marker", "empty_marker", "reading_not_kana", "unbalanced_translation")


def problem_of(old, new, before, after, count):
    """Why the new markup must not be written, or None."""
    if new.replace("{{", "").replace("}}", "") != old.replace("{{", "").replace("}}", ""):
        return "more than braces would change"
    added = after["stats"]["translations"] - before["stats"]["translations"]
    if added != count:
        return f"{added} translations more instead of {count}"
    if "untagged_translations" in before["stats"]:
        left = before["stats"]["untagged_translations"] - after["stats"]["untagged_translations"]
        if left != count:
            return f"{left} untagged translations less instead of {count}"
    for code in PROBLEMS:
        if sum(i["code"] == code for i in after["issues"]) > sum(i["code"] == code for i in before["issues"]):
            return f"new {code} issue"
    if read_back(new) != new:
        return "Odoo's HTML sanitizer would store a different markup"
    return None


def main():
    proposals = json.loads(Path(sys.argv[1]).read_text())
    write = "--apply" in sys.argv
    api = client()
    ready, skipped, wrapped = 0, [], 0
    for item_id, proposal in proposals.items():
        item = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        if item["version"] != proposal["version"]:
            skipped.append(f"#{item_id}: edited since the proposal")
            continue
        wraps = [Wrap(start, end, text, "") for start, end, text in proposal["wraps"]]
        old = item["markup"] or ""
        found = {(w.start, w.end, w.text) for w in find(old).wraps}
        if any((w.start, w.end, w.text) not in found for w in wraps):
            skipped.append(f"#{item_id}: the markup does not match the proposal")
            continue
        new = apply(old, wraps)
        before = api.post("/markup/preview", json={"markup": old}).raise_for_status().json()
        after = api.post("/markup/preview", json={"markup": new}).raise_for_status().json()
        problem = problem_of(old, new, before, after, len(wraps))
        if problem:
            skipped.append(f"#{item_id}: {problem}")
            continue
        ready += 1
        wrapped += len(wraps)
        if not write:
            continue
        response = api.patch(
            f"/comprehensives/{item_id}", json={"markup": to_send(new)}, headers={"If-Match": f'"{item["version"]}"'}
        )
        if not response.is_success:
            skipped.append(f"#{item_id}: FAILED {response.status_code} {response.text[:200]}")
            ready -= 1
            wrapped -= len(wraps)
            continue
        saved = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        status = "saved" if saved["markup"] == new else "saved, but the markup read back differs"
        print(f"#{item_id}: {status} ({len(wraps)} translations)")
    for line in skipped:
        print(line)
    print(f"{ready} of {len(proposals)} items {'written' if write else 'ready to write (dry run)'} with {wrapped} "
          f"translations, {len(skipped)} skipped")  # fmt: skip


if __name__ == "__main__":
    main()
