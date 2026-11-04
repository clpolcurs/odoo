"""fetch_all.py PATH OUT.json: every item of a paged API v1 list (limit 200), e.g. /hanviet or /vocabularies."""

import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

API = "https://oht-t4-hcet.com/api/lj/v1"
path, out = sys.argv[1], sys.argv[2]
items, cursor = [], None
while True:
    q = {"limit": 200, **({"cursor": cursor} if cursor else {})}
    url = f"{API}{path}?{urllib.parse.urlencode(q)}"
    raw = subprocess.run(["curl", "-sS", "--fail-with-body", url], capture_output=True, text=True, check=True).stdout
    page = json.loads(raw)
    items += page["items"]
    cursor = page.get("next_cursor")
    if not cursor:
        break
Path(out).write_text(json.dumps(items, ensure_ascii=False))
print(path, len(items))
