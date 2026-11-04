"""check_ocr.py RAW.json: where the transcription and Google's OCR of the same images disagree.

Japanese lines, English and Vietnamese translations and English/Vietnamese meanings are looked up in the OCR text of
the part's images (DATA/ocr/<image>.txt): furigana-only lines of the OCR are dropped, spaces ignored. Each piece is
matched with difflib; the characters of the transcription that the OCR does not have are printed, so that the image
can be checked there. Chinese is not checked (the OCR mixes in other glyphs).
"""

import difflib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

DATA = Path(os.environ.get("LJ_2400_DATA") or Path(__file__).resolve().parent / "data")
REPO = Path(__file__).resolve().parents[2]
TOKEN = re.compile(r"\{([^{}|]+)\|([^{}|]+)\}|\[\[|\]\]")
KANA_LINE = re.compile(r"^[\sぁ-ゖー・]+$")


def norm(text):
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\\[", "[").replace("\\]", "]").replace("’", "'").replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", "", text)


def ocr_of(images):
    lines = []
    for image in images:
        path = DATA / "ocr" / f"{image}.txt"
        if path.exists():
            lines += [line for line in path.read_text().splitlines() if not KANA_LINE.match(line)]
    return norm("\n".join(lines))


def missing(piece, ocr):
    """Runs of the piece that the OCR does not have (each at least 2 characters long)."""
    piece = norm(piece)
    if not piece:
        return []
    matcher = difflib.SequenceMatcher(None, piece, ocr, autojunk=False)
    covered = [False] * len(piece)
    for block in matcher.get_matching_blocks():
        if block.size >= 3:
            for i in range(block.a, block.a + block.size):
                covered[i] = True
    runs, run = [], ""
    for ch, ok in zip(piece, covered, strict=True):
        if ok:
            if len(run) >= 2:
                runs.append(run)
            run = ""
        else:
            run += ch
    if len(run) >= 2:
        runs.append(run)
    return runs


def main():
    for path in sys.argv[1:]:
        for part in json.loads(Path(path).read_text())["parts"]:
            ocr = ocr_of(part.get("images") or [])
            if not ocr:
                print(f"part {part['part']}: no OCR text")
                continue
            pieces = [
                (f"line {i + 1}", TOKEN.sub(lambda m: m.group(1) or "", line["text"]))
                for i, line in enumerate(part["lines"])
            ]
            tr = part.get("translation") or {}
            pieces += [("en", tr.get("en") or ""), ("vi", tr.get("vi") or "")]
            for word in part["words"]:
                pieces += [
                    (f"word {word['no']} en", word.get("en") or ""),
                    (f"word {word['no']} vi", word.get("vi") or ""),
                ]
            for where, piece in pieces:
                gaps = missing(piece, ocr)
                if gaps:
                    print(f"part {part['part']} {where}: {' | '.join(gaps)}")


if __name__ == "__main__":
    main()
