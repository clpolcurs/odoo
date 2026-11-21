"""Time the blocks of a listening item with the words the speech recogniser heard in its audio.

Both sides are turned into hiragana (Sudachi reads the kanji), then matched character by character with a longest
common subsequence, so the blocks the audio does not read (answer choices printed in the book, notes) and the words
the transcript leaves out (第1回, 1番) simply find no partner. A block is timed when enough of its kana are heard close
together; it starts where its first kana is heard, moved to the end of the silence just before it when there is one,
and ends where the next block starts, or a little after its last kana. A block whose first kana were not heard (an
うーん or ええ the recogniser leaves out) may start that much earlier: its start is then the first end of a silence
in that longer stretch, but never before the last kana of the block before it.

A stage direction in square brackets (［書類を確認して］) is shown but not read, so it is not looked for. A っ or ー
the recogniser does not write (え? for えっ…, ただいま for ただいまー) still counts as heard, so that a short line
is not lost for it.

Inside a timed block, every word Sudachi cuts out gets a mark (NihonGo ADR-089): when its first kana is heard, less
CHAR_SECONDS for each kana before it the recogniser left out; a sentence start is moved to the end of the silence
before it, as a block start is. A learner starts the audio from a word with it.
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
STRAY_SECONDS = 3.0  # a kana of a block heard this long before or after the next one may belong to something else
SILENT = "っー"  # kana with no sound of their own, which the recogniser often leaves out
STAGE_DIRECTION = re.compile(r"［[^］]*］|\[[^\]]*\]")  # ［書類を確認して］: shown, not read
KANJI_OR_DIGIT = re.compile(r"[々㐀-䶿一-鿿豈-﫿0-9０-９]")
SKIPPED = ("補助記号", "空白")
SENTENCE_END = re.compile(r"[。！？!?][」』）)\]]*\s*")


@dataclass(frozen=True)
class Cue:
    block: int  # index of the block in blocks_of(markup)
    text: str
    start: float  # seconds
    end: float
    ratio: float  # share of the block's kana heard
    snapped: bool  # whether the start is the end of a silence
    marks: tuple = ()  # (character of text, in code points; seconds): where the audio reaches the words inside


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
    up text like ご視聴ありがとうございました at the end of a file and gives it no time. Its times come in steps of
    0.02 s, and a word of one step is a word: ありがとうございます said quickly may get no more.
    """
    text, spans = "", []
    for word in words:
        if word["end"] - word["start"] < 0.01:
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


def without_strays(hits, sounds):
    """The hits of a block without the few kana matched far before or after the others.

    Some books read a list of words around each story (日の出, 避難する). The longest common subsequence pairs the last
    kana of a paragraph with the last such kana heard, so a word read after the story can take its end; and when the
    recogniser misses the first words of the paragraph, a word read before takes its first kana. Either way the
    paragraph seems to start or end seconds away from the rest of it. Hits are cut where STRAY_SECONDS pass without
    one; small runs at either end are dropped.
    """
    runs = [[hits[0]]]
    for previous, hit in zip(hits, hits[1:]):
        if sounds[hit[1]][1] - sounds[previous[1]][1] > STRAY_SECONDS:
            runs.append([])
        runs[-1].append(hit)
    small = max(3, 0.1 * len(hits))
    while len(runs) > 1 and len(runs[0]) < small:
        runs.pop(0)
    while len(runs) > 1 and len(runs[-1]) < small:
        runs.pop()
    return [hit for run in runs for hit in run]


def cues_of(blocks: list[Block], words, onsets, duration):
    """The cues of the blocks the audio reads, in order. onsets: ends of silences, in seconds."""
    said, owner, offsets = [], [], []
    for index, block in enumerate(blocks):
        for c, offset in reading(STAGE_DIRECTION.sub("", block.body)):
            said.append(c)
            owner.append(index)
            offsets.append(offset)
    sounds = heard(words)
    matched = {}
    for i, j in lcs(said, [c for c, _ in sounds]):
        matched.setdefault(owner[i], []).append((i, j))

    def share(index, size, hits):
        """The share of the block's kana heard, a silent kana the recogniser left out counted as heard."""
        first, taken = owner.index(index), {i for i, _ in hits}
        silent = sum(1 for i in range(first, first + size) if said[i] in SILENT and i not in taken)
        return (len(hits) + silent) / size

    found, previous_last = [], None
    for index, block in enumerate(blocks):
        size = owner.count(index)
        hits = matched.get(index, [])
        if not size or not hits or share(index, size, hits) < needed_ratio(size):
            continue
        hits = without_strays(hits, sounds)
        # Its kana must be heard close together: in no more than twice the time they take, and two seconds.
        limit = 2 * size * CHAR_SECONDS * 1.5 + 2
        ratio = share(index, size, hits)
        if ratio < needed_ratio(size) or sounds[hits[-1][1]][1] - sounds[hits[0][1]][1] > limit:
            continue
        first_i, first_j = hits[0]
        last_j = hits[-1][1]
        lead = first_i - owner.index(index)  # kana at the start of the block the recogniser did not hear
        trail = owner.index(index) + size - 1 - hits[-1][0]  # and at its end
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
        found.append((index, block, max(0.0, start), sounds[last_j][1], trail, ratio, bool(near), hits))
        previous_last = sounds[last_j][1]

    cues = []
    for k, (index, block, start, last, trail, ratio, snapped, hits) in enumerate(found):
        if cues and start < cues[-1].start:
            start = cues[-1].start
        following = found[k + 1][2] if k + 1 < len(found) else None
        end = last + TAIL_SECONDS + trail * CHAR_SECONDS  # words at the end the recogniser missed are still said
        if following is not None:
            end = min(end, max(following, start + 0.05))
        end = min(end, duration)
        if end <= start:
            continue
        first = owner.index(index)
        marks = marks_of(block, offsets[first:first + owner.count(index)], {i - first: j for i, j in hits}, sounds,
                         onsets, start, end)
        cues.append(Cue(index, block.text, round(start, 2), round(end, 2), round(ratio, 2), snapped, marks))
    return cues


def spoken_map(body):
    """The text reading() reads for a body (stage directions out, NFKC), and for each of its characters the index of the
    character of body it comes from; (None, None) when NFKC joins characters, which one at a time would not show."""
    removed = set()
    for match in STAGE_DIRECTION.finditer(body):
        removed.update(range(match.start(), match.end()))
    out, where = [], []
    for i, c in enumerate(body):
        if i in removed:
            continue
        normal = unicodedata.normalize("NFKC", c)
        out.append(normal)
        where.extend([i] * len(normal))
    text = "".join(out)
    if text != unicodedata.normalize("NFKC", STAGE_DIRECTION.sub("", body)):
        return None, None
    return text, where


def marks_of(block, offsets, hit_of, sounds, onsets, start, end):
    """The marks of a timed block (NihonGo ADR-089): for each word after the first, the character of block.text it
    starts at and when it is heard. offsets: where each kana of the block is in its spoken text; hit_of: kana of the
    block (counted from its first) to the sound heard for it. A word none of whose kana were heard has no mark, nor a
    mark that would go back in time or out of the cue."""
    spoken, where = spoken_map(block.body)
    if spoken is None:
        return ()
    prefix = len(block.text) - len(block.body)  # "F: " before what a line says
    sentence_starts = {m.end() for m in SENTENCE_END.finditer(spoken) if m.end() < len(spoken)}
    marks, previous = [], start
    for morpheme in _tokenizer().tokenize(spoken):
        begin = morpheme.begin()
        if not begin or not morpheme.surface().strip() or morpheme.part_of_speech()[0] in SKIPPED:
            continue
        after = [k for k, offset in enumerate(offsets) if offset >= begin]
        heard_k = next((k for k in after if k in hit_of), None)
        if heard_k is None:
            continue
        lead = sum(1 for k in after if k < heard_k)
        at = sounds[hit_of[heard_k]][1] - lead * CHAR_SECONDS
        if begin in sentence_starts:
            before = [sounds[hit_of[k]][1] for k in range(len(offsets)) if offsets[k] < begin and k in hit_of]
            earliest = at - SNAP_BEFORE - lead * CHAR_SECONDS * 2
            if before:
                earliest = max(earliest, before[-1] - SMEAR)
            near = [o for o in onsets if earliest <= o <= at + SNAP_AFTER]
            if near:
                at = min(near) if lead else min(near, key=lambda o: abs(o - at))
        if at < previous or at >= end:
            continue
        marks.append((prefix + where[begin], round(at, 2)))
        previous = at
    return tuple(marks)


def milliseconds(cues):
    """The cues as the API takes them, with their marks when they have some."""
    out = []
    for c in cues:
        cue = {"text": c.text, "start_ms": round(c.start * 1000), "end_ms": round(c.end * 1000)}
        # rounding may bring a mark onto the end of its cue, which the API refuses
        marks = [[at, round(seconds * 1000)] for at, seconds in c.marks]
        marks = [m for m in marks if cue["start_ms"] <= m[1] < cue["end_ms"]]
        if marks:
            cue["marks"] = marks
        out.append(cue)
    return out
