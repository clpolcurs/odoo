"""Time the blocks of a listening item with the words the speech recogniser heard in its audio.

Both sides are turned into hiragana (Sudachi reads the kanji), then matched character by character with a longest
common subsequence, so the blocks the audio does not read (answer choices printed in the book, notes) and the words
the transcript leaves out (第1回, 1番) simply find no partner. A block is timed when enough of its kana are heard close
together; it starts where its first kana is heard, moved to the end of the silence just before it when there is one,
and ends where the next block starts, or a little after its last kana. A block whose first kana were not heard (an
うーん or ええ the recogniser leaves out) may start that much earlier: its start is then the first end of a silence
in that longer stretch, but never before the last kana of the block before it.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import cache

from blocks import Block

CHAR_SECONDS = 0.11  # one kana of speech, roughly
TAIL_SECONDS = 0.6  # the last kana of a block is followed by about this much of its sound
SNAP_BEFORE, SNAP_AFTER = 0.7, 0.4  # how far an onset of speech may be from the estimated start to be taken
SMEAR = 0.15  # the recogniser often stretches the last word of a line a little into the silence after it
KANJI_OR_DIGIT = re.compile(r"[々㐀-䶿一-鿿豈-﫿0-9０-９]")
SKIPPED = ("補助記号", "空白")


@dataclass(frozen=True)
class Cue:
    block: int  # index of the block in blocks_of(markup)
    text: str
    start: float  # seconds
    end: float
    ratio: float  # share of the block's kana heard
    snapped: bool  # whether the start is the end of a silence


@cache
def _tokenizer():
    from sudachipy import Dictionary

    return Dictionary(dict="core").tokenizer()


def hiragana(text):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def _kana(surface, reading):
    form = reading if KANJI_OR_DIGIT.search(surface) else surface
    return [c for c in hiragana(form) if "ぁ" <= c <= "ゖ" or c == "ー"]


def reading(text):
    """[(kana, offset in text)] for every kana of the reading of the text."""
    out = []
    for morpheme in _tokenizer().tokenize(unicodedata.normalize("NFKC", text)):
        surface = morpheme.surface()
        if not surface.strip() or morpheme.part_of_speech()[0] in SKIPPED:
            continue
        for k, c in enumerate(_kana(surface, morpheme.reading_form())):
            out.append((c, morpheme.begin() + min(k, len(surface) - 1)))
    return out


def heard(words):
    """[(kana, seconds)]: the reading of what the recogniser heard, each kana with when it was said.

    words: [{"start", "end", "word"}] with times in seconds. A word with no length is left out: the recogniser makes
    up text like ご視聴ありがとうございました at the end of a file and gives it no time.
    """
    text, spans = "", []
    for word in words:
        if word["end"] - word["start"] < 0.02:
            continue
        start = len(text)
        text += word["word"]
        spans.append((start, len(text), word["start"], word["end"]))
    out = []
    for morpheme in _tokenizer().tokenize(text):
        surface = morpheme.surface()
        if not surface.strip() or morpheme.part_of_speech()[0] in SKIPPED:
            continue
        b, e = morpheme.begin(), morpheme.end()
        covering = [s for s in spans if s[0] < e and s[1] > b]
        if not covering:
            continue
        t0, t1 = covering[0][2], covering[-1][3]
        kana = _kana(surface, morpheme.reading_form())
        # The recogniser puts the pause before a word into the word: its speech sits at the end.
        t0 = max(t0, t1 - len(kana) * CHAR_SECONDS * 1.2)
        for k, c in enumerate(kana):
            out.append((c, t0 + (t1 - t0) * k / max(len(kana), 1)))
    return out


def lcs(a, b):
    """Index pairs (i, j) of a longest common subsequence of the sequences a and b."""
    n, m = len(a), len(b)
    rows = [[0] * (m + 1)]
    for i in range(n):
        previous, current, ai = rows[-1], [0] * (m + 1), a[i]
        for j in range(m):
            current[j + 1] = previous[j] + 1 if ai == b[j] else max(previous[j + 1], current[j])
        rows.append(current)
    pairs, i, j = [], n, m
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1] and rows[i][j] == rows[i - 1][j - 1] + 1:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif rows[i - 1][j] >= rows[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


def needed_ratio(size):
    """Share of its kana a block of `size` kana must have heard: short ones need more, so that 1. ア ウ, a choice
    the audio does not read, is not taken for the ア and ウ of other words."""
    if size <= 4:
        return 0.8
    if size >= 10:
        return 0.5
    return 0.8 - (size - 4) * 0.05


def cues_of(blocks: list[Block], words, onsets, duration):
    """The cues of the blocks the audio reads, in order. onsets: ends of silences, in seconds."""
    said, owner, offsets = [], [], []
    for index, block in enumerate(blocks):
        for c, offset in reading(block.body):
            said.append(c)
            owner.append(index)
            offsets.append(offset)
    sounds = heard(words)
    matched = {}
    for i, j in lcs(said, [c for c, _ in sounds]):
        matched.setdefault(owner[i], []).append((i, j))

    found, previous_last = [], None
    for index, block in enumerate(blocks):
        size = owner.count(index)
        hits = matched.get(index, [])
        if not size or len(hits) / size < needed_ratio(size):
            continue
        first_i, first_j = hits[0]
        last_j = hits[-1][1]
        # Its kana must be heard close together: in no more than twice the time they take, and two seconds.
        if sounds[last_j][1] - sounds[first_j][1] > 2 * size * CHAR_SECONDS * 1.5 + 2:
            continue
        lead = first_i - owner.index(index)  # kana at the start of the block the recogniser did not hear
        estimate = sounds[first_j][1] - lead * CHAR_SECONDS
        # a filler left out (うーん, ええ) is said slowly: look further back for the silence before it
        earliest = estimate - SNAP_BEFORE - lead * CHAR_SECONDS * 2
        if previous_last is not None:
            earliest = max(earliest, previous_last - SMEAR)
        near = [o for o in onsets if earliest <= o <= estimate + SNAP_AFTER]
        if not near:
            start = estimate
        elif lead:
            start = min(near)
        else:
            start = min(near, key=lambda o: abs(o - estimate))
        found.append((index, block, max(0.0, start), sounds[last_j][1], len(hits) / size, bool(near)))
        previous_last = sounds[last_j][1]

    cues = []
    for k, (index, block, start, last, ratio, snapped) in enumerate(found):
        if cues and start < cues[-1].start:
            start = cues[-1].start
        following = found[k + 1][2] if k + 1 < len(found) else None
        end = last + TAIL_SECONDS
        if following is not None:
            end = min(end, max(following, start + 0.05))
        end = min(end, duration)
        if end <= start:
            continue
        cues.append(Cue(index, block.text, round(start, 2), round(end, 2), round(ratio, 2), snapped))
    return cues


def milliseconds(cues):
    """The cues as the API takes them."""
    return [{"text": c.text, "start_ms": round(c.start * 1000), "end_ms": round(c.end * 1000)} for c in cues]
