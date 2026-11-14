"""Propose the audio cues of the published listening items of a book: which block the audio reads when.

usage: python propose.py <book id> [--model small] [--items 58,59]

Writes proposals/<book id>-<slug>.json (the cues to write, per item, with the version and audio they were made from)
and <...>_report.json (what was found per item, for the review). The audio files and what the recogniser heard go to
data/, which is not committed. An item whose audio reads few of its lines is left out of the proposal: its audio is
likely the one of another item.
"""

import argparse
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

import httpx

import align
import audio
from blocks import blocks_of

HERE = Path(__file__).parent
PROPOSALS = HERE / "proposals"
LINES_HEARD_MIN = 0.5  # share of the lines of dialogue the audio must read for the item to get cues


def client():
    base = os.environ.get("LJ_BASE_URL", "https://oht-t4-hcet.com").rstrip("/")
    key = os.environ.get("LJ_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key and not key.startswith("${") else {}
    return httpx.Client(base_url=base + "/api/lj/v1", headers=headers, timeout=120)


def read_all(api, path, params):
    items, cursor = [], None
    while True:
        page = api.get(path, params={**params, "limit": 200, "cursor": cursor}).raise_for_status().json()
        items += page["items"]
        cursor = page["next_cursor"]
        if not cursor:
            return items


def audio_file(api, item):
    """The item's audio in data/audio/<sha1>.bin, downloaded once."""
    sha1 = item["audio"]["sha1"]
    path = audio.DATA / "audio" / f"{sha1}.bin"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = api.get(f"/comprehensives/{item['id']}/audio").raise_for_status().content
        if hashlib.sha1(data).hexdigest() != sha1:
            raise RuntimeError(f"#{item['id']}: the audio downloaded is not the one of sha1 {sha1}")
        path.write_bytes(data)
    return path


def announced(words):
    """The number the audio says first (1番, 第2回 7番, じゅうごばん…), or None."""
    head = unicodedata.normalize("NFKC", "".join(w["word"] for w in words[:6]))
    match = re.search(r"(\d+)\s*番", head)
    return int(match.group(1)) if match else None


def title_number(title):
    match = re.search(r"(\d+)\s*番", unicodedata.normalize("NFKC", title or ""))
    return int(match.group(1)) if match else None


def propose_item(api, item, model):
    blocks = blocks_of(item["markup"])
    path = audio_file(api, item)
    heard = audio.recognise(path, item["audio"]["sha1"], model)
    cues = align.cues_of(blocks, heard["words"], audio.onsets(path), heard["duration"])
    lines = [i for i, b in enumerate(blocks) if b.speaker]
    timed = {c.block for c in cues}
    said, titled = announced(heard["words"]), title_number(item["title"])
    report = {
        "title": item["title"],
        "duration": round(heard["duration"], 1),
        "blocks": len(blocks),
        "lines": len(lines),
        "lines_timed": sum(i in timed for i in lines),
        "others_timed": sum(i not in lines for i in timed),
        "lines_not_timed": [blocks[i].text for i in lines if i not in timed],
        "min_ratio": min((c.ratio for c in cues), default=None),
        "not_snapped": sum(not c.snapped for c in cues),
        "announced": said,
        "cues": [
            {"block": c.block, "text": c.text, "start": c.start, "end": c.end, "ratio": c.ratio, "snapped": c.snapped}
            for c in cues
        ],
    }
    problems = []
    if lines and report["lines_timed"] < LINES_HEARD_MIN * len(lines):
        problems.append(f"the audio reads {report['lines_timed']} of {len(lines)} lines: is it the audio of this item?")
    if said is not None and titled is not None and said != titled:
        problems.append(f"the audio announces {said}番, the title is {item['title']}")
    report["problems"] = problems
    proposal = None
    if cues and not problems:
        proposal = {"title": item["title"], "version": item["version"], "audio_sha1": item["audio"]["sha1"],
                    "cues": align.milliseconds(cues)}
    return proposal, report


def slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "book"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("book", type=int)
    parser.add_argument("--model", default="small", help="faster-whisper model (small: about 4x real time on 4 CPUs)")
    parser.add_argument("--items", help="only these item ids, comma separated")
    args = parser.parse_args()

    api = client()
    book = api.get(f"/books/{args.book}").raise_for_status().json()
    items = read_all(api, "/comprehensives",
                     {"book_id": args.book, "tag": "Listening", "published": "true", "view": "full"})
    wanted = {int(i) for i in args.items.split(",")} if args.items else None
    items = [i for i in items if i.get("audio") and i.get("markup") and (wanted is None or i["id"] in wanted)]
    proposals, reports = {}, {}
    for item in sorted(items, key=lambda i: i["id"]):
        proposal, report = propose_item(api, item, args.model)
        reports[str(item["id"])] = report
        if proposal:
            proposals[str(item["id"])] = proposal
        flag = "; ".join(report["problems"]) or "ok"
        print(f"#{item['id']} {item['title']}: {len(report['cues'])} cues, lines {report['lines_timed']}/"
              f"{report['lines']}, not snapped {report['not_snapped']}, {flag}", flush=True)
    PROPOSALS.mkdir(exist_ok=True)
    name = f"{args.book}-{slug(book['name'])}"
    if wanted:
        name += "-" + "-".join(str(i) for i in sorted(wanted))
    (PROPOSALS / f"{name}.json").write_text(json.dumps(proposals, ensure_ascii=False, indent=1) + "\n")
    (PROPOSALS / f"{name}_report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1) + "\n")
    cues = sum(len(p["cues"]) for p in proposals.values())
    print(f"{len(proposals)} of {len(items)} items with {cues} cues -> proposals/{name}.json")


if __name__ == "__main__":
    main()
