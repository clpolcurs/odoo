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
# A translation may open with the Japanese term it explains: “~てならない” được sử dụng khi…, ~という dùng khi…,
# ~のみdùng khi…
_RE_TERM = re.compile(rf"^[\"'“‘(（~～「『]*[{KANA_KANJI}~～・〜]{{1,16}}[\"'”’)）」』]*(?:\s+|(?=[A-Za-zÀ-ỹĐđ]))")
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
JAPANESE_IN_TRANSLATION = 0.35  # Japanese terms outside quotes, per Latin letter
# What a translation quotes: whole Japanese examples (“留学生として”, also “…" and "…”) do not make it Japanese
_RE_QUOTED = re.compile(r"[“\"][^“”\"]*[”\"]|「[^「」]*」|『[^『』]*』")
_RE_BRACKETED = re.compile(r"\([^()]*\)|（[^（）]*）")
_ZERO_WIDTH = str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff")  # the editor leaves them between sentences
_DIALOGUE = " .…\u3000"  # the dots and spaces of a dialogue: «.....あそこです。....Ở đằng kia.»
_SENTENCE_STOP = "。！？!?"
_PAIRS = {"「": "」", "『": "』", "“": "”", "(": ")", "（": "）", '"': '"', "【": "】"}
_RE_WORD = re.compile(r"[A-Za-zÀ-ỹĐđ]{2,}")
_TERM_BEFORE_WORDS = 40  # how long the term may be that opens the translation of a sentence on the line before

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


def _unquoted(text):
    return _RE_QUOTED.sub("", text)


def vietnamese(text):
    """A Vietnamese sentence: it starts with a Vietnamese word, or with the Japanese term it explains, and holds
    Japanese only as terms and quoted examples, never a 。 of its own."""
    rest = _body(text)
    _ja, latin, vietnamese_letters = _counts(text)
    ja = len(_RE_JAPANESE.findall(_unquoted(rest)))
    return (bool(_RE_LATIN.match(rest)) and vietnamese_letters >= 1 and latin >= 4
            and ja <= JAPANESE_IN_TRANSLATION * latin and "。" not in _unquoted(text))


def _answer(text):
    """A short translation on the line of its sentence: dialogue dots, a number or quotes may come before its first
    Vietnamese word («....Ở đằng kia.», «80% doanh thu…», «871-6813 đúng không ạ.», «Là "9".»), and two letters are
    enough («Có»)."""
    rest = text.lstrip(_DIALOGUE)
    first = _RE_LATIN.search(rest)
    if not first or _RE_JAPANESE.search(rest[:first.start()]):
        return False
    _ja, latin, vietnamese_letters = _counts(rest)
    return (vietnamese_letters >= 1 and latin >= 2
            and len(_RE_JAPANESE.findall(_unquoted(rest))) <= JAPANESE_IN_TRANSLATION * latin
            and "。" not in _unquoted(rest))


def _sentence_after(text, start):
    """Where the translation that starts at `start` ends: before the next Japanese sentence of the line, with the dots,
    spaces or number that open it («Nhà vệ sinh ở đâu?     .....あそこです。», «… mấy giờ? ......7時10分です。»), or at
    the end of the line. Japanese in quotes or brackets, or that no 。 closes, belongs to the translation."""
    depth = []
    for at in range(start + 1, len(text)):
        char = text[at]
        if depth and char == _PAIRS[depth[-1]]:
            depth.pop()
        elif char in _PAIRS:
            depth.append(char)
        elif not depth and _RE_JAPANESE.match(char):
            opens = at
            while opens > start and text[opens - 1].isdigit():
                opens -= 1
            stop = opens
            while stop > start and text[stop - 1] in _DIALOGUE:
                stop -= 1
            ends = [found for found in (text.find(mark, at) for mark in _SENTENCE_STOP) if found >= 0]
            if stop < opens and ends and japanese(text[opens:min(ends) + 1]):
                return stop
    return len(text)


def _without_note(text):
    """The translation without the Japanese note in brackets that closes it: «… đấy ạ. (佐藤さんがこのワインを…。)»."""
    text = text.rstrip()
    note = re.search(r"[(（][^()（）]*[)）]$", text)
    if note and japanese(note.group(0)[1:-1]):
        return text[:note.start()].rstrip()
    return text


def _without_notes(text):
    """The Japanese sentence without the Vietnamese notes in brackets it may hold: «右に（hoặc へ）曲がります。»."""
    return _RE_BRACKETED.sub(lambda note: "" if _RE_VIETNAMESE.search(note.group(0)) else note.group(0), text)


def pairs(text):
    """Where each untagged translation of the line starts and ends: after a whole Japanese sentence, which may hold
    Vietnamese in brackets («右に（hoặc へ）曲がります。»), with the dialogue dots that open it, up to the next Japanese
    sentence: a line may hold a question and its answer, each with its translation."""
    found, head, at = [], 0, 0
    while at < len(text):
        char = text[at]
        if _RE_LATIN.match(char) or char.isdigit() or char in OPENERS or char in _DIALOGUE.strip():
            before = text[head:at].rstrip()
            sentence = _without_notes(before).rstrip()
            if sentence and before[-1] in SENTENCE_END and sentence[-1] in SENTENCE_END and japanese(sentence):
                tail = _without_note(text[at:_sentence_after(text, at)])
                if tail and (vietnamese(tail) or _answer(tail)) and not explains(before, tail.lstrip(_DIALOGUE)):
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
    rest = text[_RE_LEAD.match(text).end():]
    word = next((w for w in _RE_WORD.finditer(rest) if not w.group(0).isupper()), None)  # V, N, PI are names
    if word is None:
        return None
    term = rest[:word.start()]
    runs = re.findall(f"[{KANA_KANJI}]+", term)
    if (len(term) > _TERM_BEFORE_WORDS or not runs or _RE_VIETNAMESE.search(term) or "。" in term
            or term.rstrip().endswith((":", "：")) or not all(run in previous for run in runs)):
        return None
    return rest[word.start():]


def explains(previous, text):
    """Whether the Vietnamese line explains the line before instead of translating it: it goes on in small letters
    after the term that line ends with («「しか」<br>được dùng sau danh từ…»), or that line is a grammar term alone
    and the Vietnamese says how it is used («〜ために<br>Dùng khi…», «Vます がたい<br>Chủ yếu dùng với…»)
    rather than what it means («〜はずがない<br>Tuyệt đối không ~»)."""
    rest = _body(text)
    if rest[:1].islower() and previous.endswith(tuple("」』）)")):
        return True
    if _RE_TERM.match(text[_RE_LEAD.match(text).end():]) and not previous.rstrip().endswith(tuple(SENTENCE_END)):
        return True  # it opens with the term of the heading above it (Minna 2 #1648), not of a sentence
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
            spans = pairs(line.text)
            if spans:
                found += [line.text[start:end] for start, end in spans]
                line.claimed = True
            elif (previous is not None and not previous.translated and not previous.claimed
                  and japanese(previous.text) and (vietnamese(line.text) or _translates(previous.text, line.text))
                  and not explains(previous.text, line.text)
                  and (line.after_break or not (line.nested or previous.nested))):
                found.append(line.text)
                previous.claimed = True
        previous = line
    return found


def _translates(previous, text):
    """Whether the line translates the whole Japanese sentence before it although it opens with a term (after_term)."""
    rest = after_term(previous, text)
    return previous.rstrip().endswith(tuple(_SENTENCE_STOP)) and rest is not None and vietnamese(rest)
