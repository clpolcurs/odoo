"""compare.py A.json B.json: how far two transcriptions of the same parts agree, field by field.

Used to calibrate a cheaper transcription run against a careful one. Prints the share of identical fields and every
field that differs (with both values), so that the differences can be looked at on the image.
"""

import json
import sys
from pathlib import Path


def fields(part):
    out = {}
    for i, line in enumerate(part["lines"]):
        out[f"line {i + 1}"] = f"{line.get('speaker')}: {line['text']}"
    for word in part["words"]:
        for key in ("term", "after", "ruby", "tags", "en", "zh", "vi"):
            out[f"word {word['no']} {key}"] = word.get(key)
    for lang, text in (part.get("translation") or {}).items():
        out[f"translation {lang}"] = text
    return out


def main():
    a = {p["part"]: p for p in json.loads(Path(sys.argv[1]).read_text())["parts"]}
    b = {p["part"]: p for p in json.loads(Path(sys.argv[2]).read_text())["parts"]}
    same = total = 0
    for n in sorted(set(a) & set(b)):
        fa, fb = fields(a[n]), fields(b[n])
        for key in sorted(set(fa) | set(fb)):
            total += 1
            if fa.get(key) == fb.get(key):
                same += 1
            else:
                print(f"part {n} {key}:\n  A {fa.get(key)!r}\n  B {fb.get(key)!r}")
    print(f"{same} of {total} fields identical ({100 * same / max(total, 1):.1f}%), parts {sorted(set(a) & set(b))}")


if __name__ == "__main__":
    main()
