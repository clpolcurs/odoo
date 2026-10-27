"""Grammar matcher for NihonGo: the reference for P3, and the tool to check grammar_patterns in Odoo.

Pattern notation (one string per pattern, as stored in Odoo grammar_patterns):
  - Japanese in dictionary form: ことにする, わけだ, にすぎない. The last conjugable word of the pattern also
    matches its conjugated forms (ことにした, わけです, にすぎません).
  - "…" is a gap of up to 12 characters inside the sentence: さえ…ば, やら…やら; each piece around a gap
    must be whole words.
  - A kanji may carry a reading in brackets, checked against Sudachi: 上[じょう] (not 上[うえ]).
  - A pattern may start with what must come right before it: N (noun), Vる (dictionary form), Vた, Vて,
    Vます (masu stem), Vない, Aい, Aな. Example: Vるあまり matches 気にするあまり but not あまり～ない.
Matching runs on the surface text; a match must start at a Sudachi word boundary (so まい does not match
しまい), except right after a volitional verb (伝えよう + とする), and a pattern that does not end with a
conjugating word must also end at one (so ことか does not match ことから).
Where matches of several points overlap, the longer one that contains the others wins (に限って over
に限る, のみならず over のみ); matches of the same length are all kept.
"""

import re
from html.parser import HTMLParser

from sudachipy import Dictionary, SplitMode

TOKENIZER = Dictionary(dict="core").tokenizer(mode=SplitMode.C)
GAP = "…"
SENTENCE_END = "。！？!?\n"

# ---------- extraction of Japanese sentences and bold spans from the house markup ----------

RE_MARKER = re.compile(r"<<([^<>]*)>>")
RE_READING = re.compile(r"^(.+?)\s*-\s*(.+)$", re.DOTALL)
RE_TRANSLATION = re.compile(r"\{\{.*?\}\}", re.DOTALL)
RE_BLOCK_END = re.compile(r"</p\s*>|</li\s*>|</div\s*>|<br\s*/?>", re.IGNORECASE)
RE_JAPANESE = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")


def _base(match):
    content = match.group(1)
    reading = RE_READING.match(content)
    return (reading.group(1) if reading else content).strip()


class _Bold(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.spans, self.depth, self.start = "", [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in ("strong", "b"):
            if self.depth == 0:
                self.start = len(self.text)
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in ("strong", "b") and self.depth:
            self.depth -= 1
            if self.depth == 0 and len(self.text) > self.start:
                self.spans.append((self.start, len(self.text)))

    def handle_data(self, data):
        self.text += data


def blocks(markup):
    """[(text, [(start, end) bold spans])] for every block of the markup that holds Japanese."""
    source = RE_MARKER.sub(_base, markup or "")
    source = RE_TRANSLATION.sub(" ", source)
    out = []
    for fragment in RE_BLOCK_END.split(source):
        parser = _Bold()
        parser.feed(fragment)
        parser.close()
        text = parser.text.replace("\xa0", " ")
        if RE_JAPANESE.search(text):
            out.append((text, parser.spans))
    return out


def examples(markup):
    """Example sentences: blocks with a bold span that is not most of the block (headings)."""
    found = []
    for text, spans in blocks(markup):
        bold = sum(end - start for start, end in spans)
        if spans and bold <= 0.6 * len(text.strip()):
            found.append((text, spans))
    return found


# ---------- pattern compiler ----------

KANA_ROWS = {
    "う": "わいうえおっ",
    "く": "かきくけこい",
    "ぐ": "がぎぐげごい",
    "す": "さしすせそ",
    "つ": "たちつてとっ",
    "ぬ": "なにぬねのん",
    "ぶ": "ばびぶべぼん",
    "む": "まみむめもん",
    "る": "らりるれろっ",
}
DA = "(?:だ|です|でし|でしょ|じゃ|である|だっ|だろ|な)"
NAI = "(?:な(?:い|く|かっ|けれ|さ|し)|ませ|ず|ぬ)"
ADJ_I = "(?:い|く|かっ|けれ|さ|そ|き)"


def _stem_regex(token, previous=None):
    """Regex for the conjugated forms of the pattern's last word; only a word in dictionary form conjugates."""
    surface, pos = token.surface(), token.part_of_speech()
    ctype = pos[4]
    if surface != token.dictionary_form():
        return re.escape(surface)  # なら, で, に, だろう...: the pattern names that exact form
    if surface == "だ":
        adjectival = previous is not None and (
            previous.part_of_speech()[0] in ("形状詞", "接尾辞") or previous.surface() in ("よう", "そう", "みたい")
        )
        return DA[:-1] + "|に)" if adjectival else DA.replace("|な)", ")")
    if surface == "です":
        return "(?:です|でし|でしょ|だ|だっ|だろ)"
    if surface == "ない" and (pos[0] in ("助動詞", "形容詞")):
        return NAI
    if surface == "ます":
        return "(?:ます|まし|ませ|ましょ)"
    if ctype.startswith("サ行変格") and surface.endswith("する"):
        return re.escape(surface[:-2]) + "(?:す|し|さ|せ)"
    if ctype.startswith("カ行変格"):
        if surface.endswith("くる"):
            return re.escape(surface[:-2]) + "(?:く|き|こ|来)"
        return re.escape(surface[:-1]) + ".?"
    adjective = pos[0] == "形容詞" or ctype.startswith(("形容詞", "助動詞-タイ"))
    if adjective and surface.endswith("い"):
        return re.escape(surface[:-1]) + ADJ_I
    if ctype.startswith(("上一段", "下一段")) and surface.endswith("る"):
        # stem + a real ending, so 得る does not match 得意
        return re.escape(surface[:-1]) + "(?:る|れ|ろ|よ|な|ま|た|て|ず|ぬ|さ|ら|そう)"
    if ctype.startswith("五段"):
        last = surface[-1]
        if last in KANA_ROWS:
            return re.escape(surface[:-1]) + "[" + KANA_ROWS[last] + "]"
    return re.escape(surface)


def _segment_regex(plain):
    """(regex, ends with a whole word) of the last gap-free segment: literal except its last conjugable word."""
    tokens = list(TOKENIZER.tokenize(plain))
    if not tokens:
        return re.escape(plain), True
    last = tokens[-1]
    head = plain[: len(plain) - len(last.surface())]
    stem = _stem_regex(last, tokens[-2] if len(tokens) > 1 else None)
    return re.escape(head) + stem, stem == re.escape(last.surface())


LEFT = ("Vます", "Vない", "Vる", "Vた", "Vて", "Aい", "Aな", "N")


def _left_ok(kind, token):
    """Whether the word right before a match is what the pattern's leading placeholder asks for."""
    if token is None:
        return False
    pos, form, lemma = token.part_of_speech(), token.part_of_speech()[5], token.dictionary_form()
    if kind == "N":
        return pos[0] in ("名詞", "代名詞") or (pos[0] == "接尾辞" and pos[1].startswith("名詞"))
    if kind == "Vる":
        verbish = pos[0] == "動詞" or (pos[0] == "助動詞" and lemma in ("れる", "られる", "せる", "させる"))
        return verbish and form.startswith(("終止形", "連体形"))
    if kind == "Vた":
        return pos[0] == "助動詞" and lemma == "た"
    if kind == "Vて":
        return pos[0] == "助詞" and token.surface() in ("て", "で")
    if kind == "Vます":
        return pos[0] == "動詞" and form.startswith("連用形")
    if kind == "Vない":  # ない is an auxiliary after a verb, an adjective in ことがない
        return pos[0] in ("助動詞", "形容詞") and lemma in ("ない", "無い", "ず", "ぬ")
    if kind == "Aい":
        return pos[0] == "形容詞" and form.startswith(("終止形", "連体形"))
    if kind == "Aな":  # 残念な + ことに: the word before is な (attributive だ) or the adjective itself
        return pos[0] == "形状詞" or (token.surface() == "な" and lemma == "だ")
    return True


class Segment:
    """A gap-free piece of a pattern, with what must come right before it."""

    def __init__(self, text, last):
        self.left = next((kind for kind in LEFT if text.startswith(kind)), None)
        body = text[len(self.left) :] if self.left else text
        self.readings = re.findall(r"(\S)\[([^\]]+)\]", body)
        plain = re.sub(r"\[[^\]]+\]", "", body)
        if last:
            self.regex, self.literal_end = _segment_regex(plain)
        else:  # an inner segment ends where the gap starts: exact text
            self.regex, self.literal_end = re.escape(plain), True
        self.volitional = body.startswith(("よう", "う"))


class Pattern:
    def __init__(self, text):
        self.text = text.strip()
        parts = [part for part in self.text.split(GAP) if part]
        self.segments = [Segment(part, index == len(parts) - 1) for index, part in enumerate(parts)]
        gap = "[^" + SENTENCE_END + "]{0,12}?"
        self.regex = re.compile(gap.join("(" + seg.regex + ")" for seg in self.segments))


def _hira(text):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


class Analysed:
    """A sentence with its Sudachi words, to check word boundaries and readings."""

    def __init__(self, text):
        self.text = text
        self.tokens = list(TOKENIZER.tokenize(text))
        self.starts = {t.begin() for t in self.tokens}
        self.ends = {t.end() for t in self.tokens}
        self.ending_at = {t.end(): t for t in self.tokens}

    def token_at(self, pos):
        for t in self.tokens:
            if t.begin() <= pos < t.end():
                return t
        return None

    def matches(self, pattern):
        found = []
        for m in pattern.regex.finditer(self.text):
            if all(
                self._segment_ok(seg, m.start(i + 1), m.end(i + 1), first=(i == 0))
                for i, seg in enumerate(pattern.segments)
            ):
                found.append((m.start(), m.end()))
        return found

    def _segment_ok(self, seg, start, end, first):
        if start not in self.starts:
            inside = self.token_at(start)
            if not (
                first and seg.volitional and inside is not None and inside.part_of_speech()[5].startswith("意志推量形")
            ):
                return False
        if seg.literal_end and end not in self.ends:
            return False
        if seg.left and not _left_ok(seg.left, self.ending_at.get(start)):
            return False
        return not seg.readings or self._readings_ok(seg.readings, start, end)

    def _readings_ok(self, readings, start, end):
        for char, reading in readings:
            pos = self.text.find(char, start, end)
            token = self.token_at(pos) if pos >= 0 else None
            if token is None or reading not in _hira(token.reading_form()):
                return False
        return True


def compile_all(patterns):
    return [Pattern(p) for p in patterns if p.strip()]


def resolve(found):
    """found: [(point, pattern, start, end)] in one sentence; drop matches contained in a longer match of
    another point (same-length overlaps are all kept). A match with a gap (…) never hides another one."""
    keep = []
    for f in found:
        _, _, s, e = f
        if not any(
            o[0] != f[0] and GAP not in o[1] and o[2] <= s and e <= o[3] and (o[3] - o[2]) > (e - s) for o in found
        ):
            keep.append(f)
    return keep
