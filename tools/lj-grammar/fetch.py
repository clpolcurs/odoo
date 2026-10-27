"""Download what evaluate.py needs from the learning_japanese API into data/.

  data/grammar_items.json  grammar points of the books published to NihonGo (full items)
  data/corpus.json         sentences of the published reading and listening items

The API key comes from LJ_API_KEY, or from a network secret of the Claude Code cloud environment (then
LJ_API_KEY stays empty and no Authorization header is sent).
"""

import json
import os
import re
from pathlib import Path

import httpx

from gmatch import RE_JAPANESE, blocks

DATA = Path(__file__).parent / "data"


def client():
    base = os.environ.get("LJ_BASE_URL", "https://oht-t4-hcet.com").rstrip("/")
    key = os.environ.get("LJ_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key and not key.startswith("${") else {}
    return httpx.Client(base_url=base + "/api/lj/v1", headers=headers, timeout=120)


def read_all(api, params):
    items, cursor = [], None
    while True:
        page = api.get("/comprehensives", params={**params, "view": "full", "limit": 200, "cursor": cursor})
        page.raise_for_status()
        items += page.json()["items"]
        cursor = page.json()["next_cursor"]
        if not cursor:
            return items


def main():
    DATA.mkdir(exist_ok=True)
    api = client()
    grammar = read_all(api, {"grammar": "true", "published": "true"})
    (DATA / "grammar_items.json").write_text(json.dumps(grammar, ensure_ascii=False, indent=1))
    sentences = []
    for item in read_all(api, {"tag": "Reading,Listening", "published": "true"}):
        for text, _ in blocks(item["markup"] or ""):
            for sentence in re.split(r"(?<=[。！？])", text):
                if RE_JAPANESE.search(sentence):
                    sentences.append({"item": item["id"], "level": item["level"], "text": sentence.strip()})
    (DATA / "corpus.json").write_text(json.dumps(sentences, ensure_ascii=False))
    print(f"{len(grammar)} grammar points, {len(sentences)} corpus sentences -> {DATA}")


if __name__ == "__main__":
    main()
