"""Save approved grammar_patterns to Odoo, one PATCH per point that changes.

usage: python apply.py proposals/<file>.json            show what would change
       python apply.py proposals/<file>.json --apply    write it (If-Match: the version just read)

Only run --apply on patterns the content owner approved.
"""

import json
import sys
from pathlib import Path

from fetch import client


def main():
    proposals = json.loads(Path(sys.argv[1]).read_text())
    write = "--apply" in sys.argv
    api = client()
    changed = 0
    for item_id, patterns in proposals.items():
        item = api.get(f"/comprehensives/{item_id}").raise_for_status().json()
        if item["grammar_patterns"] == patterns:
            continue
        changed += 1
        if not write:
            print(f"#{item_id}: {item['grammar_patterns']} -> {patterns}")
            continue
        response = api.patch(
            f"/comprehensives/{item_id}",
            json={"grammar_patterns": patterns},
            headers={"If-Match": f'"{item["version"]}"'},
        )
        status = "saved" if response.is_success else f"FAILED {response.status_code} {response.text[:200]}"
        print(f"#{item_id}: {status}")
    print(f"{changed} of {len(proposals)} points {'written' if write else 'would change (dry run)'}")


if __name__ == "__main__":
    main()
