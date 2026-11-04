"""check_readings.py RAW.json [RAW.json ...]: furigana of the transcription that Sudachi reads differently.

Each line of a story is read by Sudachi (mode C); a `{漢字|よみ}` whose kanji form one kanji run of a token is
compared with the reading Sudachi gives that run. Entries are checked the same way, in their dictionary form.
Differences are not errors by themselves (the book is right more often than Sudachi), but each one is worth a look
at the image. Run with: uv run --project ../lj-readings python check_readings.py ...
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lj-readings"))
from readings import align, hiragana
from sudachipy import Dictionary, SplitMode

TOKEN = re.compile(r"\{([^{}|]+)\|([^{}|]+)\}|\[\[|\]\]")
TOKENIZER = Dictionary().create()


def spans(text):
    """(plain text, [(start, end, base, reading)])"""
    plain, out, pos = [], [], 0
    length = 0
    for m in TOKEN.finditer(text):
        chunk = text[pos : m.start()]
        plain.append(chunk)
        length += len(chunk)
        if m.group(1):
            out.append((length, length + len(m.group(1)), m.group(1), m.group(2)))
            plain.append(m.group(1))
            length += len(m.group(1))
        pos = m.end()
    plain.append(text[pos:])
    return "".join(plain), out


def sudachi_runs(plain):
    """{(start, end): reading} for every kanji run Sudachi can align with its reading."""
    runs = {}
    for token in TOKENIZER.tokenize(plain, SplitMode.C):
        surface, start = token.surface(), token.begin()
        aligned = align(surface, hiragana(token.reading_form()))
        if aligned:
            for offset, size, reading in aligned:
                runs[(start + offset, start + offset + size)] = reading
    return runs


def check_text(text, where, found):
    plain, marked = spans(text)
    runs = sudachi_runs(plain)
    for start, end, base, reading in marked:
        guess = runs.get((start, end))
        if guess is not None and guess != reading:
            found.append(f"{where}: {base} {reading} (Sudachi {guess}) in …{plain[max(0, start - 8) : end + 8]}…")


def main():
    found = []
    for path in sys.argv[1:]:
        for part in json.loads(Path(path).read_text())["parts"]:
            for i, line in enumerate(part["lines"]):
                check_text(line["text"], f"part {part['part']} line {i + 1}", found)
            for word in part["words"]:
                if word.get("ruby"):
                    check_text(word["ruby"], f"word {word['no']}", found)
    print("\n".join(found) or "no difference")
    print(f"{len(found)} differences", file=sys.stderr)


if __name__ == "__main__":
    main()
