"""Check proposed grammar_patterns: recall on each point's own examples, hits in the reading corpus.

usage: python evaluate.py proposals/<file>.json [--show-noise N]   (after fetch.py)
A proposals file maps item ids to patterns: {"2393": ["Vることだ", "Vないことだ"], ...}.
Writes <file>_report.json next to it and prints one line per point: patterns, examples matched / examples,
corpus sentences matched, missed examples (MISSED) and examples won by another point's longer match (SHADOWED).
Examples are the bold spans of the point's sentences; for books that bold nothing, its numbered lines and
dialogues, each whole (marked "no bold").
"""

import json
import sys
from collections import Counter
from pathlib import Path

from gmatch import Analysed, compile_all, point_examples, resolve

DATA = Path(__file__).parent / "data"


def load_corpus():
    return [Analysed(s["text"]) for s in json.loads((DATA / "corpus.json").read_text())]


def _hits(found, spans):
    """Whether one of the matches overlaps a bold span of the example."""
    return any(f[2] < e and s < f[3] for f in found for s, e in spans)


def evaluate(proposals, corpus, show_noise=0):
    items = {str(i["id"]): i for i in json.loads((DATA / "grammar_items.json").read_text())}
    compiled = {pid: compile_all(patterns) for pid, patterns in proposals.items()}

    def all_matches(sentence):
        return [(pid, p.text, s, e) for pid, ps in compiled.items() for p in ps for s, e in sentence.matches(p)]

    corpus_hits, samples = Counter(), {}
    for sentence in corpus:
        kept = resolve(all_matches(sentence))
        for pid, ptext, s, e in {(f[0], f[1]): f for f in kept}.values():  # one count per sentence and pattern
            corpus_hits[pid, ptext] += 1
            bucket = samples.setdefault((pid, ptext), [])
            if len(bucket) < show_noise:
                bucket.append(sentence.text[max(0, s - 12) : e + 8])
    rows = []
    for pid, patterns in proposals.items():
        item = items[pid]
        found_examples, bold = point_examples(item["markup"])
        exs = [(Analysed(text), spans) for text, spans in found_examples]
        missed, shadowed = [], []
        for sentence, spans in exs:
            found = all_matches(sentence)
            own = [f for f in found if f[0] == pid]
            if not _hits(own, spans):
                shown = sentence.text.strip().replace("\n", " ")
                marked = "".join(sentence.text[s:e] for s, e in spans)
                missed.append(f"{marked} ⟨{shown[:40]}⟩" if bold else shown[:50])
            elif not _hits([f for f in resolve(found) if f[0] == pid], spans):
                winners = {f[0] for f in resolve(found) if f[0] != pid}
                shadowed.append(sentence.text.strip()[:30] + " → #" + ",#".join(sorted(winners)))
        rows.append(
            {
                "id": pid,
                "title": item["title"].replace("\n", " ⏎ "),
                "patterns": patterns,
                "examples": len(exs),
                "bold": bool(bold),
                "recall": len(exs) - len(missed),
                "missed": missed,
                "shadowed": shadowed,
                "corpus": {p: corpus_hits[pid, p] for p in patterns if corpus_hits[pid, p]},
                "samples": {p: samples.get((pid, p), []) for p in patterns if samples.get((pid, p))},
            }
        )
    return rows


def main():
    proposals = json.loads(Path(sys.argv[1]).read_text())
    show = int(sys.argv[sys.argv.index("--show-noise") + 1]) if "--show-noise" in sys.argv else 0
    rows = evaluate(proposals, load_corpus(), show)
    report = Path(sys.argv[1]).with_name(Path(sys.argv[1]).stem + "_report.json")
    report.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    low = [r for r in rows if r["examples"] and r["recall"] < r["examples"]]
    matched, total = sum(r["recall"] for r in rows), sum(r["examples"] for r in rows)
    without = sum(1 for r in rows if not r["examples"])
    unmarked = sum(1 for r in rows if r["examples"] and not r["bold"])
    print(
        f"{len(rows)} points; examples matched {matched}/{total}; {len(low)} points miss some examples; "
        f"{without} points have no examples; {unmarked} use numbered lines (no bold)"
    )
    for r in rows:
        flag = ""
        if r["recall"] < r["examples"]:
            flag = f"  MISSED {r['examples'] - r['recall']}: " + " | ".join(r["missed"][:3])
        if r["shadowed"]:
            flag += "  SHADOWED: " + " | ".join(r["shadowed"][:2])
        hits = ", ".join(f"{p}={n}" for p, n in r["corpus"].items())
        patterns, score = " ; ".join(r["patterns"]), f"{r['recall']}/{r['examples']}"
        if not r["bold"]:
            score += " no bold"
        print(f"#{r['id']} {r['title'][:38]} :: {patterns} :: {score} :: corpus {hits or 0}{flag}")
        for p, s in r["samples"].items():
            for sample in s:
                print(f"      {p}: …{sample}…")


if __name__ == "__main__":
    main()
