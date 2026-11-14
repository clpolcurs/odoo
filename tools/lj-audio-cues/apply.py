"""Write approved audio cue proposals to Odoo, one PUT /comprehensives/<id>/audio-cues per item.

usage: python apply.py proposals/<book>.json            check every item against Odoo, write nothing
       python apply.py proposals/<book>.json --apply    write it (If-Match: the version the proposal was made from)

An item edited since the proposal was made, or whose audio changed, is skipped: run propose.py again for it. Every cue
must still name a block of the item's markup, in order. After writing, the cues are read back and compared. Only run
--apply on proposals the content owner approved.
"""

import json
import sys
from pathlib import Path

from blocks import blocks_of, key
from propose import client


def unmatched(markup, cues):
    """The texts of the cues that name no block of the markup, looked for in order as NihonGo does."""
    keys = [key(block.text) for block in blocks_of(markup)]
    missing, at = [], 0
    for cue in cues:
        wanted = key(cue["text"])
        found = next((i for i in range(at, len(keys)) if keys[i] == wanted), None)
        if found is None:
            missing.append(cue["text"])
        else:
            at = found + 1
    return missing


def main():
    proposals = json.loads(Path(sys.argv[1]).read_text())
    write = "--apply" in sys.argv
    api = client()
    ready, done, skipped = 0, 0, []
    for item_id, proposal in proposals.items():
        item = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        wanted = {"audio_sha1": proposal["audio_sha1"], "cues": proposal["cues"]}
        if item.get("audio_cues") == wanted:
            done += 1
            continue
        if item["version"] != proposal["version"]:
            skipped.append(f"#{item_id}: edited since the proposal")
            continue
        if (item.get("audio") or {}).get("sha1") != proposal["audio_sha1"]:
            skipped.append(f"#{item_id}: its audio changed since the proposal")
            continue
        missing = unmatched(item["markup"], proposal["cues"])
        if missing:
            skipped.append(f"#{item_id}: {len(missing)} cues name no block, e.g. {missing[0][:30]}")
            continue
        ready += 1
        if not write:
            continue
        response = api.put(f"/comprehensives/{item_id}/audio-cues", json=wanted,
                           headers={"If-Match": f'"{item["version"]}"'})
        if not response.is_success:
            skipped.append(f"#{item_id}: FAILED {response.status_code} {response.text[:200]}")
            ready -= 1
            continue
        saved = api.get(f"/comprehensives/{item_id}/audio-cues").raise_for_status().json()["audio_cues"]
        print(f"#{item_id}: {'saved' if saved == wanted else 'saved, but the cues read back differ'} "
              f"({len(proposal['cues'])} cues)")
    for line in skipped:
        print(line)
    action = "written" if write else "ready to write (dry run)"
    print(f"{ready} of {len(proposals)} items {action}, {done} already had these cues, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
