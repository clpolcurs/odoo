"""Download the published reading, listening and grammar items with their markup into data/items.json.

The API key comes from LJ_API_KEY, or from a network secret of the Claude Code cloud environment (then
LJ_API_KEY stays empty and no Authorization header is sent).
"""

import json
import os
from pathlib import Path

import httpx

DATA = Path(__file__).parent / "data"
TAGS = "Reading,Listening,Grammar"  # what /qa/issues checks by default


def client():
    base = os.environ.get("LJ_BASE_URL", "https://oht-t4-hcet.com").rstrip("/")
    key = os.environ.get("LJ_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key and not key.startswith("${") else {}
    return httpx.Client(base_url=base + "/api/lj/v1", headers=headers, timeout=120)


def read_all(api, path, params):
    items, cursor = [], None
    while True:
        page = api.get(path, params={**params, "limit": 200, "cursor": cursor})
        page.raise_for_status()
        items += page.json()["items"]
        cursor = page.json()["next_cursor"]
        if not cursor:
            return items


def main():
    DATA.mkdir(exist_ok=True)
    api = client()
    items = read_all(api, "/comprehensives", {"published": "true", "tag": TAGS, "view": "full"})
    books = read_all(api, "/books", {})
    (DATA / "items.json").write_text(json.dumps(items, ensure_ascii=False))
    (DATA / "books.json").write_text(json.dumps(books, ensure_ascii=False, indent=1))
    print(f"{len(items)} published items, {len(books)} books -> {DATA}")


if __name__ == "__main__":
    main()
