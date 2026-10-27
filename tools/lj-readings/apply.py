"""Write approved reading proposals to Odoo, one PATCH per item.

usage: python apply.py proposals/<book>.json            check every item against Odoo, write nothing
       python apply.py proposals/<book>.json --apply    write it (If-Match: the version the proposal was made from)

An item edited after the proposal was made is skipped: run fetch.py and propose.py again for it. Before writing,
the new markup must show the same text (but for the typos the proposal fixes), have exactly one explicit reading
more per proposed marker, no new markup problem in /markup/preview, and come back unchanged through Odoo's HTML
sanitizer (odoo_html.py). Only run --apply on proposals the content owner approved.
"""

import json
import sys
from pathlib import Path

from fetch import client
from odoo_html import read_back, to_send
from readings import Fix, Marker, apply, paragraphs

PROBLEMS = ("unbalanced_marker", "empty_marker", "reading_not_kana", "unbalanced_translation")


def visible_text(markup):
    return [p.text for p in paragraphs(markup)]


def problem_of(old, new, fixed, before, after, count):
    """Why the new markup must not be written, or None; fixed is the old markup with only its typos fixed."""
    if visible_text(new) != visible_text(fixed):
        return "the visible text would change beyond the typo fixes"
    added = after["stats"]["explicit_readings"] - before["stats"]["explicit_readings"]
    if added != count:
        return f"{added} readings instead of {count}"
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
    ready, skipped, left = 0, [], [0, 0]
    for item_id, proposal in proposals.items():
        item = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        if item["version"] != proposal["version"]:
            skipped.append(f"#{item_id}: edited since the proposal")
            continue
        markers = [Marker(start, end, text, reading, "") for start, end, text, reading in proposal["markers"]]
        fixes = [Fix(*fix, why="") for fix in proposal.get("fixes", [])]
        old = item["markup"] or ""
        new = apply(old, markers, fixes)
        before = api.post("/markup/preview", json={"markup": old}).raise_for_status().json()
        after = api.post("/markup/preview", json={"markup": new}).raise_for_status().json()
        problem = problem_of(old, new, apply(old, [], fixes), before, after, len(markers))
        for i, check in enumerate((before, after)):
            left[i] += sum(issue["code"] == "kanji_without_reading" for issue in check["issues"])
        if problem:
            skipped.append(f"#{item_id}: {problem}")
            continue
        ready += 1
        if not write:
            continue
        response = api.patch(
            f"/comprehensives/{item_id}", json={"markup": to_send(new)}, headers={"If-Match": f'"{item["version"]}"'}
        )
        if not response.is_success:
            skipped.append(f"#{item_id}: FAILED {response.status_code} {response.text[:200]}")
            ready -= 1
            continue
        saved = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        status = "saved" if saved["markup"] == new else "saved, but the markup read back differs"
        print(f"#{item_id}: {status} ({len(markers)} readings)")
    for line in skipped:
        print(line)
    total = len(proposals)
    print(f"{ready} of {total} items {'written' if write else 'ready to write (dry run)'}, {len(skipped)} skipped; "
          f"kanji without reading: {left[0]} -> {left[1]}")  # fmt: skip


if __name__ == "__main__":
    main()
