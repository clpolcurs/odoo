"""Grammar matcher for NihonGo: the reference for P3, and the tool to check grammar_patterns in Odoo.

Pattern notation (one string per pattern, as stored in Odoo grammar_patterns):
  - Japanese in dictionary form: ことにする, わけだ, にすぎない. The last conjugable word of the pattern also
    matches its conjugated forms (ことにした, わけです, にすぎません); ない also matches ありません
    (わけではありません), and a verb suffix does not match its noun form (ぶる does not match 10年ぶり).
  - "…" is a gap of up to 12 characters inside the sentence: さえ…ば, やら…やら; each piece around a gap
    must be whole words.
  - A kanji may carry a reading in brackets, checked against Sudachi: 上[じょう] (not 上[うえ]); a word may
    carry its part of speech the same way: と[接続助詞] is the と of 着くと, not of 行くと思う.
  - A pattern may start with what must come right before it: N (noun), Vる (dictionary form; not いう of
    という, so Vることだ does not match ということだ), Vた (also 泳いだ), Vて, Vます (masu stem), Vない,
    Aい (also 出やすい), Aく (寂しく), A (the stem: 辛 of 辛そう), Aな. Example: Vるあまり matches
    気にするあまり but not あまり～ない.
Matching runs on the surface text (zero-width and word-separating spaces dropped); a match must start at a
Sudachi word boundary (so まい does not match しまい), except right after a volitional verb (伝えよう + とする),
and a pattern that does not end with a
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
RE_SPAN = re.compile(r"</?span\b[^>]*>", re.IGNORECASE)
RE_READING = re.compile(r"^(.+?)\s*-\s*(.+)$", re.DOTALL)
RE_TRANSLATION = re.compile(r"\{\{.*?\}\}", re.DOTALL)
RE_BLOCK_END = re.compile(r"</p\s*>|</li\s*>|</div\s*>|<br\s*/?>", re.IGNORECASE)
RE_JAPANESE = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")
RE_LATIN = re.compile(r"[A-Za-zÀ-ỹ]")
RE_KANA = re.compile(r"^[ぁ-ゟ゠-ヿ]+$")
RE_INVISIBLE = re.compile("[\u200b-\u200d\u2060\ufeff]")  # zero-width spaces split words: お手洗い\u200bは
RE_SPACED = re.compile(r"(?<=[぀-ヿ㐀-䶿一-鿿])[ \u3000]+(?=[぀-ヿ㐀-䶿一-鿿])")  # 分かち書き: が あります


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
    source = RE_MARKER.sub(_base, RE_SPAN.sub("", markup or ""))  # <<前<span>\u200b</span>に>>: color spans only
    source = RE_TRANSLATION.sub(" ", source)
    out = []
    for fragment in RE_BLOCK_END.split(source):
        parser = _Bold()
        parser.feed(fragment)
        parser.close()
        text = RE_SPACED.sub("", RE_INVISIBLE.sub("", parser.text.replace("\xa0", " ")))
        if RE_JAPANESE.search(text):
            out.append((text, parser.spans))
    return out


def examples(markup):
    """Example sentences: Japanese blocks with a bold span that is not most of the block (headings)."""
    found = []
    for text, spans in blocks(markup):
        bold = sum(end - start for start, end in spans)
        vietnamese = len(RE_LATIN.findall(text)) > len(RE_JAPANESE.findall(text))
        if spans and bold <= 0.6 * len(text.strip()) and not vietnamese:
            found.append((text, spans))
    return found


def point_examples(markup):
    """(examples, bold): the bold examples of a point, or its unmarked ones when the book bolds (almost) nothing,
    so that a stray bold word does not hide the examples."""
    bold, unmarked = examples(markup), unmarked_examples(markup)
    return (bold, True) if bold and len(bold) * 2 >= len(unmarked) else (unmarked, False)


RE_NUMBER = re.compile(r"^([0-9０-９]+)(?:\s*[.．]|\s)\s*")
RE_SPEAKER = re.compile(r"^([A-ZＡ-Ｚ]|[^\s:：]{1,4})\s*[:：]")
RE_TRANSLATED = re.compile(r"[。？！?!][\s.…]*(?=[A-Za-zÀ-ỹ])(?![A-ZＡ-Ｚ]\s*[:：])")  # です。Tôi là..., not B:
RE_SAMPLE = re.compile(r"^例\s*[0-9０-９]*\s*[.．:：]?")  # the worked answer of an exercise
RE_ANSWER = re.compile(r"^[.．…・]{2,}")  # ……はい、そうです。: the answer to the example before it
EXERCISE = "やってみよう"


def _speaker(line):
    """A: or B: that a dialogue line starts with, after its number if it has one."""
    number = RE_NUMBER.match(line)
    speaker = RE_SPEAKER.match(line[number.end() :] if number else line)
    return speaker.group(1) if speaker else None


def unmarked_examples(markup):
    """Examples of books that bold nothing, each whole: numbered lines and dialogues (A: / B: lines, one example
    each); for a point that has none of them, the sentences followed by their Vietnamese translation on the same
    line (私は学生です。Tôi là sinh viên.). A translation on the line is cut off. Exercises hold wrong sentences on
    purpose, so they are left out: from やってみよう to the next explanation or heading, or to where the numbering
    starts again at 1."""
    found, loose, dialogue = [], [], []
    exercise, last = False, 0

    def close_dialogue():
        if dialogue:
            text = "\n".join(dialogue)
            found.append((text, [(0, len(text))]))
            dialogue.clear()

    for text, spans in blocks(markup):
        line = text.strip()
        heading = sum(end - start for start, end in spans) > 0.6 * len(line)
        translated = RE_TRANSLATED.search(line)
        if translated:
            line = line[: translated.start() + 1]
        japanese = len(RE_LATIN.findall(line)) <= len(RE_JAPANESE.findall(line))
        number, speaker = RE_NUMBER.match(line), _speaker(line)
        if RE_SAMPLE.match(line):
            continue
        if RE_ANSWER.match(line) and japanese and not exercise:
            if dialogue:
                dialogue.append(line)
                continue
            target = found if found and not loose else (loose or found)
            if target:
                text = target[-1][0] + "\n" + line
                target[-1] = (text, [(0, len(text))])
                continue
        if EXERCISE in line or heading or not (number or speaker):
            close_dialogue()
            exercise, last = EXERCISE in line, 0
            if translated and japanese and not heading:
                loose.append((line, [(0, len(line))]))
            continue
        if number:
            if exercise and last and int(number.group(1)) == 1:
                exercise = False
            last = int(number.group(1))
        if exercise or not japanese:  # Vietnamese
            continue
        if number or not speaker or (dialogue and _speaker(dialogue[0]) == speaker):  # a new example
            close_dialogue()
        if speaker:
            dialogue.append(line)
        else:
            found.append((line, [(0, len(line))]))
    close_dialogue()
    return found or loose


# ---------- pattern compiler ----------

KANA_ROWS = {
    "う": "わいうえおっ",
    "く": "かきくけこいっ",  # 行く: 行って
    "ぐ": "がぎぐげごい",
    "す": "さしすせそ",
    "つ": "たちつてとっ",
    "ぬ": "なにぬねのん",
    "ぶ": "ばびぶべぼん",
    "む": "まみむめもん",
    "る": "らりるれろっい",  # くださる, いらっしゃる: くださいます
}
DA = "(?:だ|です|でし|でしょ|じゃ|である|だっ|だろ|な)"
NAI = "(?:な(?:い|く|かっ|けれ|さ|し)|ませ|ありませ|ございませ|ず|ぬ)"  # ではない -> ではありません
ADJ_I = "(?:い|く|かっ|けれ|さ|そ|き)"


COPULA = ("copula", None)


def _stem_regex(token, previous=None):
    """(regex, check) for the conjugated forms of the pattern's last word; only a word in dictionary form
    conjugates. check says what the sentence word there must be: ("lemma", 従う) for a word that conjugates by
    its own endings (でる does not match the で of 原因で, ぶる not 10年ぶり), COPULA for だ and です (not the だ of
    読んだ)."""
    surface, pos = token.surface(), token.part_of_speech()
    ctype = pos[4]
    if surface != token.dictionary_form():
        return re.escape(surface), None  # なら, で, に, だろう...: the pattern names that exact form
    if surface == "だ":
        adjectival = previous is not None and (
            previous.part_of_speech()[0] in ("形状詞", "接尾辞") or previous.surface() in ("よう", "そう", "みたい")
        )
        return (DA[:-1] + "|に)" if adjectival else DA.replace("|な)", ")")), COPULA
    if surface == "です":
        return "(?:です|でし|でしょ|だ|だっ|だろ)", COPULA
    if surface == "ない" and (pos[0] in ("助動詞", "形容詞")):
        return NAI, None
    if surface == "ます":
        return "(?:ます|まし|ませ|ましょ)", None
    lemma = ("lemma", (token.dictionary_form(), token.normalized_form()))
    if ctype.startswith("サ行変格") and surface.endswith("する"):
        return re.escape(surface[:-2]) + "(?:す|し|さ|せ)", lemma
    if ctype.startswith("カ行変格"):
        if surface.endswith("くる"):
            return re.escape(surface[:-2]) + "(?:く|き|こ|来)", lemma
        return re.escape(surface[:-1]) + ".?", lemma
    adjective = pos[0] == "形容詞" or ctype.startswith(("形容詞", "助動詞-タイ", "助動詞-ラシイ"))
    if adjective and surface.endswith("い"):
        return re.escape(surface[:-1]) + ADJ_I, lemma
    if ctype.startswith(("上一段", "下一段", "助動詞-レル")) and surface.endswith("る"):
        return re.escape(surface[:-1]) + "(?:る|れ|ろ|よ|な|ま|た|て|ず|ぬ|さ|ら|そう)", lemma
    if ctype.startswith("五段") and surface[-1] in KANA_ROWS:
        return re.escape(surface[:-1]) + "[" + KANA_ROWS[surface[-1]] + "]", lemma
    return re.escape(surface), None


def _segment_regex(plain):
    """(regex, ends with a whole word, check) of the last gap-free segment: literal except its last conjugable
    word, which is the group "last"."""
    tokens = list(TOKENIZER.tokenize(plain))
    if not tokens:
        return re.escape(plain), True, None
    last = tokens[-1]
    head = plain[: len(plain) - len(last.surface())]
    stem, check = _stem_regex(last, tokens[-2] if len(tokens) > 1 else None)
    if check is None:
        return re.escape(head) + stem, stem == re.escape(last.surface()), None
    return re.escape(head) + "(?P<last>" + stem + ")", False, check


LEFT = ("Vます", "Vない", "Vる", "Vた", "Vて", "Aい", "Aく", "Aな", "A", "N")


def _verbish(token):
    """A verb, or an auxiliary that conjugates like one: れる, られる, せる, させる."""
    pos = token.part_of_speech()
    return pos[0] == "動詞" or (pos[0] == "助動詞" and token.dictionary_form() in ("れる", "られる", "せる", "させる"))


def _left_ok(kind, token):
    """Whether the word right before a match is what the pattern's leading placeholder asks for."""
    if token is None:
        return False
    pos, form, lemma = token.part_of_speech(), token.part_of_speech()[5], token.dictionary_form()
    if kind == "N":
        return pos[0] in ("名詞", "代名詞") or (pos[0] == "接尾辞" and pos[1].startswith("名詞"))
    if kind == "Vる":  # not いう of という, そういう: ということだ is hearsay, not Vることだ
        return _verbish(token) and form.startswith(("終止形", "連体形")) and token.surface() != "いう"
    if kind == "Vた":  # た, and だ of 泳いだ (its lemma is だ)
        return pos[0] == "助動詞" and pos[4] == "助動詞-タ"
    if kind == "Vて":
        return pos[0] == "助詞" and token.surface() in ("て", "で")
    if kind == "Vます":  # also られ of 食べられそう
        return _verbish(token) and form.startswith("連用形")
    if kind == "Vない":  # ない is an auxiliary after a verb, an adjective in ことがない
        return pos[0] in ("助動詞", "形容詞") and lemma in ("ない", "無い", "ず", "ぬ")
    adjective = pos[0] == "形容詞" or (pos[0] == "接尾辞" and pos[1] == "形容詞的")  # also 出やすい, 分かりにくい
    if kind == "Aい":
        return adjective and form.startswith(("終止形", "連体形"))
    if kind == "Aく":  # 寂しくなんかない, 大きくなる
        return adjective and form.startswith("連用形")
    if kind == "A":  # the stem: 辛そう, 大き過ぎる, 良さそう
        return adjective and form.startswith("語幹")
    if kind == "Aな":  # 残念な + ことに: the word before is な (attributive だ) or the adjective itself (親切 is
        # a noun that can be a na-adjective for Sudachi)
        na_adjective = pos[0] == "形状詞" or (pos[0] == "名詞" and pos[2] == "形状詞可能")
        return na_adjective or (token.surface() == "な" and lemma == "だ")
    return True


class Segment:
    """A gap-free piece of a pattern, with what must come right before it."""

    def __init__(self, text, last):
        self.left = next((kind for kind in LEFT if text.startswith(kind)), None)
        body = text[len(self.left) :] if self.left else text
        self.readings = re.findall(r"(\S)\[([^\]]+)\]", body)
        plain = re.sub(r"\[[^\]]+\]", "", body)
        if last:
            self.regex, self.literal_end, self.check = _segment_regex(plain)
        else:  # an inner segment ends where the gap starts: exact text
            self.regex, self.literal_end, self.check = re.escape(plain), True, None
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
            ) and self._last_word_ok(pattern.segments[-1].check, m):
                found.append((m.start(), m.end()))
        return found

    def _last_word_ok(self, check, m):
        """The conjugated last word of the pattern is that same word in the sentence."""
        if check is None:
            return True
        token = self.token_at(m.start("last"))
        if token is None:
            return False
        if check is COPULA:
            return token.part_of_speech()[4] in ("助動詞-ダ", "助動詞-デス")
        dictionary, normalized = check[1]  # すむ is 住む, 済む or 澄む: its kana form is enough
        return token.dictionary_form() == dictionary or token.normalized_form() == normalized

    def _segment_ok(self, seg, start, end, first):
        if start not in self.starts:
            inside = self.token_at(start)
            if not (
                first
                and seg.volitional
                and inside is not None
                and _verbish(inside)  # 休もう, 打ち上げられよう, not でしょう or ましょう
                and inside.part_of_speech()[5].startswith("意志推量形")
            ):
                return False
        if seg.literal_end and end not in self.ends:
            return False
        if seg.left and not _left_ok(seg.left, self.ending_at.get(start)):
            return False
        return not seg.readings or self._readings_ok(seg.readings, start, end)

    def _readings_ok(self, readings, start, end):
        """上[じょう]: the word holding 上 reads じょう; と[接続助詞]: the word holding と is a 接続助詞."""
        for char, wanted in readings:
            pos = self.text.find(char, start, end)
            token = self.token_at(pos) if pos >= 0 else None
            if token is None:
                return False
            if RE_KANA.match(wanted):
                if wanted not in _hira(token.reading_form()):
                    return False
            elif wanted not in token.part_of_speech()[:2]:
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
