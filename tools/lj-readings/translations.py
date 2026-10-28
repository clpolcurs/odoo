"""Vietnamese translations written outside {{...}} (QA issue untagged_translation) and the {{...}} that fix them.

The rules are those of custom_addons/learning_japanese/services/translations.py, which reports the issue; keep the
two in step. Here every character of a line also knows where it comes from in the markup, so that a proposal can put
"{{" before the translation and "}}" after it without touching anything else.
"""

import html
import re
from dataclasses import dataclass, field

KANA_KANJI = "ぁ-ゖァ-ヺー㐀-䶿一-鿿豈-﫿々〆ヶ"
RE_JAPANESE = re.compile(f"[{KANA_KANJI}]")
RE_LATIN = re.compile(r"[A-Za-zÀ-ỹĐđ]")
RE_VIETNAMESE = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.IGNORECASE)
RE_LEAD = re.compile(
    rf"^\s*(?:[0-9０-９]{{1,3}}\s*[.)．、:]?\s*|[a-dA-Dａ-ｄ][.)]?\s+|[A-ZＡ-Ｚ][0-9]?\s*[:：]\s*"
    rf"|[{KANA_KANJI}]{{1,6}}\s*[:：]\s*|\w{{1,6}}\s*[:：]\s*|[・･•*＊]\s*)*"
)
SENTENCE_END = "。！？!?」』）)"
OPENERS = "\"'“‘(（~～[［"
RE_TERM = re.compile(rf"^[\"'“‘(（~～「『]*[{KANA_KANJI}~～・〜]{{1,16}}[\"'”’)）」』]*(?:\s+|(?=[A-Za-zÀ-ỹĐđ]))")
RE_TERM_LINE = re.compile(
    rf"^(?:[(（]\s*[0-9０-９]{{1,2}}\s*[)）]|[0-9０-９]{{1,2}}\s*[.)．])?[\s「『\"“{KANA_KANJI}～〜~・／/（）()VN]{{1,24}}"
    rf"[」』\"”]*$"
)
RE_TERM_MARK = re.compile(r"[～〜~]|[VN][ぁ-ゖ]")
RE_EXPLAINING = re.compile(
    r"^(?:(?:chủ yếu|thường|cũng|chỉ) )?(?:được )?(?:dùng|sử dụng|diễn tả|diễn đạt|biểu thị|biểu hiện|thể hiện)\b"
    r"|^đây là\b|^là (?:cách|hình thức|thể)\b",
    re.IGNORECASE,
)
JAPANESE_IN_TRANSLATION = 0.35
RE_QUOTED = re.compile(r"[“\"][^“”\"]*[”\"]|「[^「」]*」|『[^『』]*』")  # also “…" and "…”
RE_BRACKETED = re.compile(r"\([^()]*\)|（[^（）]*）")
ZERO_WIDTH = str.maketrans("", "", "​‌‍⁠﻿")
DIALOGUE = " .…　"  # the dots and spaces of a dialogue: «.....あそこです。....Ở đằng kia.»
SENTENCE_STOP = "。！？!?"
PAIRS = {"「": "」", "『": "』", "“": "”", "(": ")", "（": "）", '"': '"', "【": "】"}
RE_WORD = re.compile(r"[A-Za-zÀ-ỹĐđ]{2,}")
TERM_BEFORE_WORDS = 40  # how long the term may be that opens the translation of a sentence on the line before

RE_TOKEN = re.compile(r"\{\{.*?\}\}|<<[^<>]*>>|<[^<>]*>|&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z]+);|[^<{&]+|[<{&]", re.DOTALL)
RE_TAG_NAME = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9]*)")
RE_READING = re.compile(r"^(.+?)\s*-\s*(.+)$", re.DOTALL)
LINE_ENDS = {"p", "div", "li", "td", "th", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol", "table"}
VOID = {"br", "img", "hr", "input", "wbr", "col", "source"}


def counts(text):
    return len(RE_JAPANESE.findall(text)), len(RE_LATIN.findall(text)), len(RE_VIETNAMESE.findall(text))


def japanese(text):
    ja, _latin, vietnamese_letters = counts(text)
    return ja >= 2 and vietnamese_letters == 0


def body(text):
    """The text from its first Vietnamese word: without the number or speaker before it, or the term it explains."""
    rest = text[RE_LEAD.match(text).end() :]
    term = RE_TERM.match(rest)
    return rest[term.end() :] if term else rest.lstrip(OPENERS)


def unquoted(text):
    """The text without what it quotes: a translation may quote whole Japanese examples (“留学生として”)."""
    return RE_QUOTED.sub("", text)


def vietnamese(text):
    """A Vietnamese sentence: it starts with a Vietnamese word, or with the Japanese term it explains, and holds
    Japanese only as terms and quoted examples, never a 。 of its own."""
    rest = body(text)
    _ja, latin, vietnamese_letters = counts(text)
    ja = len(RE_JAPANESE.findall(unquoted(rest)))
    return (
        bool(RE_LATIN.match(rest))
        and vietnamese_letters >= 1
        and latin >= 4
        and ja <= JAPANESE_IN_TRANSLATION * latin
        and "。" not in unquoted(text)
    )


def answer(text):
    """A short translation on the line of its sentence: dialogue dots, a number or quotes may come before its first
    Vietnamese word («....Ở đằng kia.», «80% doanh thu…», «871-6813 đúng không ạ.», «Là "9".»), and two letters are
    enough («Có»)."""
    rest = text.lstrip(DIALOGUE)
    first = RE_LATIN.search(rest)
    if not first or RE_JAPANESE.search(rest[: first.start()]):
        return False
    _ja, latin, vietnamese_letters = counts(rest)
    return (
        vietnamese_letters >= 1
        and latin >= 2
        and len(RE_JAPANESE.findall(unquoted(rest))) <= JAPANESE_IN_TRANSLATION * latin
        and "。" not in unquoted(rest)
    )


def sentence_after(text, start):
    """Where the translation that starts at `start` ends: before the next Japanese sentence of the line, with the dots,
    spaces or number that open it («Nhà vệ sinh ở đâu?     .....あそこです。», «… mấy giờ? ......7時10分です。»), or at
    the end of the line. Japanese in quotes or brackets, or that no 。 closes, belongs to the translation."""
    depth = []
    for at in range(start + 1, len(text)):
        char = text[at]
        if depth and char == PAIRS[depth[-1]]:
            depth.pop()
        elif char in PAIRS:
            depth.append(char)
        elif not depth and RE_JAPANESE.match(char):
            opens = at
            while opens > start and text[opens - 1].isdigit():
                opens -= 1
            stop = opens
            while stop > start and text[stop - 1] in DIALOGUE:
                stop -= 1
            ends = [found for found in (text.find(mark, at) for mark in SENTENCE_STOP) if found >= 0]
            if stop < opens and ends and japanese(text[opens : min(ends) + 1]):
                return stop
    return len(text)


def without_note(text):
    """The translation without the Japanese note in brackets that closes it: «… đấy ạ. (佐藤さんがこのワインを…。)»."""
    text = text.rstrip()
    note = re.search(r"[(（][^()（）]*[)）]$", text)
    if note and japanese(note.group(0)[1:-1]):
        return text[: note.start()].rstrip()
    return text


def without_notes(text):
    """The Japanese sentence without the Vietnamese notes in brackets it may hold: «右に（hoặc へ）曲がります。»."""
    return RE_BRACKETED.sub(lambda note: "" if RE_VIETNAMESE.search(note.group(0)) else note.group(0), text)


def pairs(text):
    """Where each untagged translation of the line starts and ends: after a whole Japanese sentence, which may hold
    Vietnamese in brackets («右に（hoặc へ）曲がります。»), with the dialogue dots that open it, up to the next Japanese
    sentence: a line may hold a question and its answer, each with its translation."""
    found, head, at = [], 0, 0
    while at < len(text):
        char = text[at]
        if RE_LATIN.match(char) or char.isdigit() or char in OPENERS or char in DIALOGUE.strip():
            before = text[head:at].rstrip()
            sentence = without_notes(before).rstrip()
            if sentence and before[-1] in SENTENCE_END and sentence[-1] in SENTENCE_END and japanese(sentence):
                tail = without_note(text[at : sentence_after(text, at)])
                if tail and (vietnamese(tail) or answer(tail)) and not explains(before, tail.lstrip(DIALOGUE)):
                    found.append((at, at + len(tail)))
                    head = at = at + len(tail)
                    continue
        at += 1
    return found


def split(text):
    """Where the first untagged translation of a Japanese sentence starts on the same line, or None."""
    found = pairs(text)
    return found[0][0] if found else None


def after_term(previous, text):
    """The translation of the sentence on the line before, from its first Vietnamese word, when it opens with the term
    that sentence explains: «「～による・～によって」は、…表す。<br>～による/～によって thể hiện…»,
    «“お/ご~願います” được sử dụng…», «〜と、... sử dụng…»; or None. Every Japanese run of the term is in that
    sentence, and a term with a colon is a gloss («～ている: …»)."""
    rest = text[RE_LEAD.match(text).end() :]
    word = next((w for w in RE_WORD.finditer(rest) if not w.group(0).isupper()), None)  # V, N, PI are names
    if word is None:
        return None
    term = rest[: word.start()]
    runs = re.findall(f"[{KANA_KANJI}]+", term)
    if (
        len(term) > TERM_BEFORE_WORDS
        or not runs
        or RE_VIETNAMESE.search(term)
        or "。" in term
        or term.rstrip().endswith((":", "："))
        or not all(run in previous for run in runs)
    ):
        return None
    return rest[word.start() :]


def explains(previous, text):
    """Whether the Vietnamese line explains the line before instead of translating it: it goes on in small letters
    after the term that line ends with («「しか」<br>được dùng sau danh từ…»), or that line is a grammar term alone
    and the Vietnamese says how it is used («〜ために<br>Dùng khi…», «Vます がたい<br>Chủ yếu dùng với…»)
    rather than what it means («〜はずがない<br>Tuyệt đối không ~»)."""
    rest = body(text)
    if rest[:1].islower() and previous.endswith(tuple("」』）)")):
        return True
    if RE_TERM.match(text[RE_LEAD.match(text).end() :]) and not previous.rstrip().endswith(tuple(SENTENCE_END)):
        return True  # it opens with the term of the heading above it (Minna 2 #1648), not of a sentence
    return bool(RE_TERM_LINE.match(previous) and RE_TERM_MARK.search(previous) and RE_EXPLAINING.match(rest))


@dataclass
class Line:
    text: str = ""
    spans: list = field(default_factory=list)  # (start, end) in the markup of each character of text
    translated: bool = False
    after_break: bool = False
    nested: bool = False
    claimed: bool = False
    braces: list = field(default_factory=list)  # (start, end) in the markup of each {{...}}, and how much text before

    def stripped(self):
        """The line without its outer white space, with the spans that go with it."""
        start, end = 0, len(self.text)
        while start < end and self.text[start].isspace():
            start += 1
        while end > start and self.text[end - 1].isspace():
            end -= 1
        braces = [(left, right, min(max(at - start, 0), end - start)) for left, right, at in self.braces]
        return Line(
            self.text[start:end], self.spans[start:end], self.translated, self.after_break, self.nested, False, braces
        )


def lines(markup):
    """The lines of the markup, as the addon cuts them: blocks and <br> end them, tags and zero-width characters give
    no text, markers give their words, translations their place; code blocks are left out."""
    out, line, cells, items, code = [], Line(), 0, 0, 0

    def end(after_break):
        nonlocal line
        out.append(line.stripped())
        line = Line(after_break=after_break, nested=cells > 0 or items > 0)

    def add(text, start, stop):
        text = text.translate(ZERO_WIDTH)
        if not code:
            line.text += text
            line.spans += [(start, stop)] * len(text)

    for token in RE_TOKEN.finditer(markup or ""):
        value, start, stop = token.group(0), token.start(), token.end()
        if value.startswith("{{") and value.endswith("}}") and len(value) > 3:
            line.translated = line.translated or not code
            if not code:
                line.braces.append((start, stop, len(line.text)))
        elif value.startswith("<<") and value.endswith(">>"):
            reading = RE_READING.match(value[2:-2])
            add((reading.group(1) if reading else value[2:-2]).strip(), start, stop)
        elif value.startswith("&") and value.endswith(";"):
            add(html.unescape(value).replace("\xa0", " "), start, stop)
        elif value.startswith("<") and (tag := RE_TAG_NAME.match(value)):
            closing, name = tag.group(1) == "/", tag.group(2).lower()
            if name in ("pre", "code"):
                code = max(code + (-1 if closing else 1), 0)
            elif name == "br":
                end(after_break=True)
            else:
                if name in ("td", "th"):
                    cells += -1 if closing else 1
                elif name == "li":
                    items += -1 if closing else 1
                if name in LINE_ENDS:
                    end(after_break=False)
        else:
            for offset, char in enumerate(value):
                add(char.replace("\xa0", " "), start + offset, start + offset + 1)
    end(after_break=False)
    return [line for line in out if line.text or line.translated]


@dataclass
class Wrap:
    start: int  # markup offsets: "{{" goes before start, "}}" after end
    end: int
    text: str  # the translation as it reads
    rule: str  # "same line" or "next line"
    before: str = ""  # the Japanese it translates, for the review


@dataclass
class Unwrap:
    start: int  # markup offsets of the "{{" and of the end of the "}}" that come off
    end: int
    text: str  # what the braces hold, as it reads
    before: str = ""  # the term it explains, for the review


@dataclass
class Found:
    wraps: list = field(default_factory=list)
    doubts: list = field(default_factory=list)  # (text, why): translations a person must wrap by hand


def balanced(fragment):
    """Whether the tags of a markup fragment close inside it: braces around it keep the HTML well formed."""
    depth = 0
    for tag in RE_TAG_NAME.finditer(fragment):
        name = tag.group(2).lower()
        if name in VOID:
            continue
        if tag.group(1) == "/":
            depth -= 1
            if depth < 0:
                return False
        else:
            depth += 1
    return depth == 0


def find(markup):
    """The {{...}} the markup is missing, line by line, with the same rules as the QA issue."""
    found, previous = Found(), None
    for line in lines(markup):
        if not line.translated:
            spans = [(at, stop, "same line") for at, stop in pairs(line.text)]
            if not spans and (
                previous is not None
                and not previous.translated
                and not previous.claimed
                and japanese(previous.text)
                and (
                    vietnamese(line.text)
                    or (translates(previous) and vietnamese(after_term(previous.text, line.text) or ""))
                )
                and not explains(previous.text, line.text)
                and (line.after_break or not (line.nested or previous.nested))
            ):
                spans = [(0, len(line.text), "next line")]
            head = 0
            for at, stop, rule in spans:
                (previous if rule == "next line" else line).claimed = True
                before = previous.text if rule == "next line" else line.text[head:at].strip()
                text, head = line.text[at:stop], stop
                start, end = line.spans[at][0], line.spans[stop - 1][1]
                if "{" in markup[start:end] or "}" in markup[start:end]:
                    found.doubts.append((text, "chứa dấu { hoặc }"))
                elif not balanced(markup[start:end]):
                    found.doubts.append((text, "định dạng (đậm, màu…) cắt ngang bản dịch"))
                else:
                    found.wraps.append(Wrap(start, end, text, rule, before))
        previous = line
    return found


def explanations(markup):
    """The {{...}} that hold the Vietnamese explanation of a grammar term instead of a translation (explains()): the
    braces hide it from the Nội dung tab of Odoo. The rules wrote such braces before they knew explains().

    A line that repeats the term before its braces, under a Japanese sentence with no translation of its own, is the
    translation of that sentence and keeps its braces: «「～させられる」は、…使う。<br>「～させられる」{{sử dụng khi…}}»
    (Try N2, Try N3)."""
    found, previous = [], None
    for line in lines(markup):
        for start, end, at in line.braces:
            text = " ".join(inner.text for inner in lines(markup[start + 2 : end - 2]) if inner.text)
            before = line.text[:at].strip() if at else (previous.text if previous is not None else "")
            if at and translates(previous):
                continue
            if before and japanese(before) and vietnamese(text) and explains(before, text):
                found.append(Unwrap(start, end, text, before))
        if line.text:
            previous = line
    return found


def translates(previous):
    """Whether the line after this one may be its translation: a whole Japanese sentence without its own."""
    return (
        previous is not None
        and not previous.translated
        and japanese(previous.text)
        and previous.text.rstrip().endswith(tuple("。！？!?"))
    )


def apply(markup, wraps, unwraps=()):
    """The markup with braces around the wraps and without the braces of the unwraps."""
    edits = [(w.start, w.end, True) for w in wraps] + [(u.start, u.end, False) for u in unwraps]
    for start, end, wrap in sorted(edits, reverse=True):
        inner = "{{" + markup[start:end] + "}}" if wrap else markup[start + 2 : end - 2]
        markup = markup[:start] + inner + markup[end:]
    return markup
