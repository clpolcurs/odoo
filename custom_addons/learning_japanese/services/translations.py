"""Vietnamese translations written outside `{{...}}`: the QA issue `untagged_translation`.

The markup puts the Vietnamese translation of a sentence in `{{...}}`: the Nội dung tab of Odoo leaves it out and
NihonGo shows it on demand. Many items write it as plain text instead, after the Japanese sentence on the same line
(`日本語の文。Câu tiếng Việt.`) or on the next line (`日本語の文。<br>Câu tiếng Việt.`). This module finds those
translations; tools/lj-readings proposes the `{{...}}` with the same rules (keep the two in step).

Explanations written in Vietnamese around Japanese terms (`できます biểu thị năng lực…`) are not translations: a
translation follows a whole Japanese sentence and starts with a Vietnamese word.
"""

import html
import re
from dataclasses import dataclass

KANA_KANJI = "ぁ-ゖァ-ヺー㐀-䶿一-鿿豈-﫿々〆ヶ"
_RE_JAPANESE = re.compile(f"[{KANA_KANJI}]")
_RE_LATIN = re.compile(r"[A-Za-zÀ-ỹĐđ]")
_RE_VIETNAMESE = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.IGNORECASE
)
# What may open a line before its words: numbers, letters, speakers and bullets ("1. ", "a ", "A: ", "佐藤: ",
# "Nam: ", "・", "* ").
_RE_LEAD = re.compile(
    rf"^\s*(?:[0-9０-９]{{1,3}}\s*[.)．、:]?\s*|[a-dA-Dａ-ｄ][.)]?\s+|[A-ZＡ-Ｚ][0-9]?\s*[:：]\s*"
    rf"|[{KANA_KANJI}]{{1,6}}\s*[:：]\s*|\w{{1,6}}\s*[:：]\s*|[・･•*＊]\s*)*"
)
SENTENCE_END = "。！？!?」』）)"
OPENERS = "\"'“‘(（~～[［"
# A translation may open with the Japanese term it explains: “~てならない” được sử dụng khi…, ~という dùng khi…
_RE_TERM = re.compile(rf"^[\"'“‘(（~～「『]*[{KANA_KANJI}~～・〜]{{1,10}}[\"'”’)）」』]*\s+")
# A grammar term alone on its line (〜ために, お〜ください, Vます がたい) and how an explanation of it starts
_RE_TERM_LINE = re.compile(
    rf"^(?:[(（]\s*[0-9０-９]{{1,2}}\s*[)）]|[0-9０-９]{{1,2}}\s*[.)．])?[\s「『\"“{KANA_KANJI}～〜~・／/（）()VN]{{1,24}}"
    rf"[」』\"”]*$",
)
_RE_TERM_MARK = re.compile(r"[～〜~]|[VN][ぁ-ゖ]")
_RE_EXPLAINING = re.compile(
    r"^(?:(?:chủ yếu|thường|cũng|chỉ) )?(?:được )?(?:dùng|sử dụng|diễn tả|diễn đạt|biểu thị|biểu hiện|thể hiện)\b"
    r"|^đây là\b|^là (?:cách|hình thức|thể)\b",
    re.IGNORECASE,
)
JAPANESE_IN_TRANSLATION = 0.35  # quoted Japanese terms, per Latin letter
_ZERO_WIDTH = str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff")  # the editor leaves them between sentences

_RE_TOKEN = re.compile(r"\{\{.*?\}\}|<<[^<>]*>>|<[^<>]*>|[^<{]+|[<{]", re.DOTALL)
_RE_TAG_NAME = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9]*)")
_RE_READING = re.compile(r"^(.+?)\s*-\s*(.+)$", re.DOTALL)
_LINE_ENDS = {"p", "div", "li", "td", "th", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol",
              "table"}


def _counts(text):
    return len(_RE_JAPANESE.findall(text)), len(_RE_LATIN.findall(text)), len(_RE_VIETNAMESE.findall(text))


def japanese(text):
    """A Japanese sentence: kana or kanji, Latin letters only as names (DVD, IPS), no Vietnamese letter."""
    ja, _latin, vietnamese_letters = _counts(text)
    return ja >= 2 and vietnamese_letters == 0


def _body(text):
    """The text from its first Vietnamese word: without the number or speaker before it, or the term it explains."""
    rest = text[_RE_LEAD.match(text).end():]
    term = _RE_TERM.match(rest)
    return rest[term.end():] if term else rest.lstrip(OPENERS)


def vietnamese(text):
    """A Vietnamese sentence: it starts with a Vietnamese word, or with the Japanese term it explains, and holds
    Japanese only as quoted terms, never a 。."""
    ja, latin, vietnamese_letters = _counts(text)
    return (bool(_RE_LATIN.match(_body(text))) and vietnamese_letters >= 1 and latin >= 4
            and ja <= JAPANESE_IN_TRANSLATION * latin and "。" not in text)


def split(text):
    """Where the untagged translation of a Japanese sentence starts on the same line, or None."""
    for at, char in enumerate(text):
        if not (_RE_LATIN.match(char) or char.isdigit() or char in OPENERS):
            continue
        head = text[:at].rstrip()
        if (head and head[-1] in SENTENCE_END and japanese(head) and vietnamese(text[at:])
                and not explains(head, text[at:])):
            return at
    return None


def explains(previous, text):
    """Whether the Vietnamese line explains the line before instead of translating it: it goes on in small letters
    after the term that line ends with («「しか」<br>được dùng sau danh từ…»), or that line is a grammar term alone
    and the Vietnamese says how it is used («〜ために<br>Dùng khi…», «Vます がたい<br>Chủ yếu dùng với…»)
    rather than what it means («〜はずがない<br>Tuyệt đối không ~»)."""
    rest = _body(text)
    if rest[:1].islower() and previous.endswith(tuple("」』）)")):
        return True
    return bool(_RE_TERM_LINE.match(previous) and _RE_TERM_MARK.search(previous) and _RE_EXPLAINING.match(rest))


@dataclass
class Line:
    text: str = ""
    translated: bool = False  # the line holds a {{...}}
    after_break: bool = False  # a <br> of the same block comes before it
    nested: bool = False  # it is in a table cell or a list item, where a line does not translate the one before
    claimed: bool = False  # its translation was found


def lines(markup):
    """The lines of the markup: blocks and <br> end them; tags and zero-width characters go, markers give their
    words, translations their place. Code blocks are left out."""
    out, line, cells, items = [], Line(), 0, 0

    def end(after_break):
        nonlocal line
        line.text = html.unescape(line.text).translate(_ZERO_WIDTH).replace("\xa0", " ").strip()
        out.append(line)
        line = Line(after_break=after_break, nested=cells > 0 or items > 0)

    code = 0
    for token in _RE_TOKEN.findall(markup or ""):
        if token.startswith("{{") and token.endswith("}}") and len(token) > 3:
            line.translated = line.translated or not code
            continue
        if token.startswith("<<") and token.endswith(">>"):
            if not code:
                reading = _RE_READING.match(token[2:-2])
                line.text += (reading.group(1) if reading else token[2:-2]).strip()
            continue
        tag = _RE_TAG_NAME.match(token) if token.startswith("<") else None
        if not tag:
            if not code:
                line.text += token
            continue
        closing, name = tag.group(1) == "/", tag.group(2).lower()
        if name in ("pre", "code"):
            code += -1 if closing else 1
            code = max(code, 0)
            continue
        if name == "br":
            end(after_break=True)
            continue
        if name in ("td", "th"):
            cells += -1 if closing else 1
        elif name == "li":
            items += -1 if closing else 1
        if name in _LINE_ENDS:
            end(after_break=False)
            line.nested = cells > 0 or items > 0
    end(after_break=False)
    return [line for line in out if line.text or line.translated]


def untagged(markup):
    """The Vietnamese translations of the markup that are not in {{...}}, as written."""
    found, previous = [], None
    for line in lines(markup):
        if not line.translated:
            at = split(line.text)
            if at is not None:
                found.append(line.text[at:])
                line.claimed = True
            elif (previous is not None and not previous.translated and not previous.claimed
                  and japanese(previous.text) and vietnamese(line.text) and not explains(previous.text, line.text)
                  and (line.after_break or not (line.nested or previous.nested))):
                found.append(line.text)
                previous.claimed = True
        previous = line
    return found
