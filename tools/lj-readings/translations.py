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
RE_VIETNAMESE = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.IGNORECASE
)
RE_LEAD = re.compile(
    rf"^\s*(?:[0-9０-９]{{1,3}}\s*[.)．、:]?\s*|[a-dA-Dａ-ｄ][.)]?\s+|[A-ZＡ-Ｚ][0-9]?\s*[:：]\s*"
    rf"|[{KANA_KANJI}]{{1,6}}\s*[:：]\s*|\w{{1,6}}\s*[:：]\s*)*"
)
SENTENCE_END = "。！？!?」』）)"
OPENERS = "\"'“‘(（~～"
RE_TERM = re.compile(rf"^[\"'“‘(（~～「『]*[{KANA_KANJI}~～・〜]{{1,10}}[\"'”’)）」』]*\s+")
JAPANESE_IN_TRANSLATION = 0.35

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


def vietnamese(text):
    body = text[RE_LEAD.match(text).end() :]
    term = RE_TERM.match(body)
    body = body[term.end() :] if term else body.lstrip(OPENERS)
    ja, latin, vietnamese_letters = counts(text)
    return (
        bool(RE_LATIN.match(body))
        and vietnamese_letters >= 1
        and latin >= 4
        and ja <= JAPANESE_IN_TRANSLATION * latin
        and "。" not in text
    )


def split(text):
    """Where the untagged translation of a Japanese sentence starts on the same line, or None."""
    for at, char in enumerate(text):
        if not (RE_LATIN.match(char) or char.isdigit() or char in OPENERS):
            continue
        head = text[:at].rstrip()
        if head and head[-1] in SENTENCE_END and japanese(head) and vietnamese(text[at:]):
            return at
    return None


@dataclass
class Line:
    text: str = ""
    spans: list = field(default_factory=list)  # (start, end) in the markup of each character of text
    translated: bool = False
    after_break: bool = False
    nested: bool = False
    claimed: bool = False

    def stripped(self):
        """The line without its outer white space, with the spans that go with it."""
        start, end = 0, len(self.text)
        while start < end and self.text[start].isspace():
            start += 1
        while end > start and self.text[end - 1].isspace():
            end -= 1
        return Line(self.text[start:end], self.spans[start:end], self.translated, self.after_break, self.nested)


def lines(markup):
    """The lines of the markup, as the addon cuts them: blocks and <br> end them, tags give no text, markers give
    their words, translations their place; code blocks are left out."""
    out, line, cells, items, code = [], Line(), 0, 0, 0

    def end(after_break):
        nonlocal line
        out.append(line.stripped())
        line = Line(after_break=after_break, nested=cells > 0 or items > 0)

    def add(text, start, stop):
        if not code:
            line.text += text
            line.spans += [(start, stop)] * len(text)

    for token in RE_TOKEN.finditer(markup or ""):
        value, start, stop = token.group(0), token.start(), token.end()
        if value.startswith("{{") and value.endswith("}}") and len(value) > 3:
            line.translated = line.translated or not code
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
            at, rule = split(line.text), "same line"
            if at is None and (
                previous is not None
                and not previous.translated
                and not previous.claimed
                and japanese(previous.text)
                and vietnamese(line.text)
                and (line.after_break or not (line.nested or previous.nested))
            ):
                at, rule = 0, "next line"
            if at is not None:
                (previous if rule == "next line" else line).claimed = True
                before = previous.text if rule == "next line" else line.text[:at].strip()
                text = line.text[at:]
                start, end = line.spans[at][0], line.spans[-1][1]
                if "{" in markup[start:end] or "}" in markup[start:end]:
                    found.doubts.append((text, "chứa dấu { hoặc }"))
                elif not balanced(markup[start:end]):
                    found.doubts.append((text, "định dạng (đậm, màu…) cắt ngang bản dịch"))
                else:
                    found.wraps.append(Wrap(start, end, text, rule, before))
        previous = line
    return found


def apply(markup, wraps):
    for wrap in sorted(wraps, key=lambda w: w.start, reverse=True):
        markup = markup[: wrap.start] + "{{" + markup[wrap.start : wrap.end] + "}}" + markup[wrap.end :]
    return markup
