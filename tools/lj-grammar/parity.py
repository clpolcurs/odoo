"""Write the fixture the Java matcher of NihonGo must reproduce (GrammarParityTests in clpolcurs/nihongo).

  uv run python parity.py ../../../nihongo/services/api/src/test/resources/grammar/parity.json.gz

Reads data/ as fetch.py left it: every pattern of the grammar points, matched over the sentences of the published
reading and listening items and the examples of the grammar points, each sentence once. Offsets are in code points.
"""

import gzip
import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from gmatch import Analysed, compile_all, point_examples, resolve

HERE = Path(__file__).parent
DATA = HERE / "data"


def fixture():
    items = json.loads((DATA / "grammar_items.json").read_text())
    points = [
        {"id": item["id"], "patterns": item["grammar_patterns"]} for item in items if item.get("grammar_patterns")
    ]
    compiled = [(point["id"], pattern) for point in points for pattern in compile_all(point["patterns"])]
    corpus = [sentence["text"] for sentence in json.loads((DATA / "corpus.json").read_text())]
    examples = [text for item in items for text, _ in point_examples(item["markup"])[0]]
    sentences = list(dict.fromkeys(corpus + examples))
    expected = []
    for index, text in enumerate(sentences):
        analysed = Analysed(text)
        kept = resolve(
            [
                (point, pattern.text, start, end)
                for point, pattern in compiled
                for start, end in analysed.matches(pattern)
            ]
        )
        if kept:
            expected.append({"sentence": index, "matches": [list(match) for match in kept]})
    # The last commit that changed the matcher, not HEAD: an unrelated commit leaves the fixture as it is.
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%h", "--", "gmatch.py"], capture_output=True, text=True, cwd=HERE
    ).stdout.strip()
    about = (
        f"Grammar matches of tools/lj-grammar/gmatch.py (clpolcurs/odoo {commit}) with sudachipy "
        f"{version('sudachipy')} and SudachiDict core {version('sudachidict_core')}, mode C: the reference the "
        "Java matcher must reproduce. Offsets in code points."
    )
    return {"about": about, "points": points, "sentences": sentences, "expected": expected}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    data = fixture()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    Path(sys.argv[1]).write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
    total = sum(len(row["matches"]) for row in data["expected"])
    print(f"{len(data['sentences'])} sentences, {len(data['points'])} points: {total} matches -> {sys.argv[1]}")


if __name__ == "__main__":
    main()
