"""The text blocks of the markup of a listening item, cut the way NihonGo cuts them.

NihonGo (services/api, MarkupConverter) turns the markup into blocks and puts each cue on the block whose text is the
cue's, compared without spaces and with full-width forms folded (NFKC). So a cue must carry the text of one block as
NihonGo shows it, and this module follows its rules:

- p, div, h1-h6, blockquote, li and the other block elements end a block; <br> breaks a line inside one;
- <<漢字 - よみ>> shows 漢字, <<漢字>> shows 漢字, {{...}} is a translation and shows nothing;
- <rt>, <rp>, <script>, <style> show nothing;
- a table whose rows all read speaker, colon, text is dialogue: one block a row; any other table is no text block,
  so no cue can land on it;
- a block opening with a speaker (F:, M:, 木山：) is a line of dialogue: NihonGo shows it as "F: text".
"""

import html
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser

ESCAPED_MARKER = re.compile(r"&lt;&lt;((?:(?!&[lg]t;)[^<>])+)(?:&gt;&gt;|>>)")
MARKER = re.compile(r"<<([^<>]*)>>")
READING = re.compile(r"^(.+?)\s*-\s*(.+)$", re.S)
OTHER_TRANSLATION = re.compile(r"(?:<br\s*/?>\s*)?\{\{\s*(?:en|zh)\s*:.*?\}\}", re.S | re.I)
TRANSLATION = re.compile(r"\{\{.*?\}\}", re.S)
STRAY_LT = re.compile(r"<(?![A-Za-z/!?])")
JAPANESE = "々぀-ヿ㐀-䶿一-鿿豈-﫿"
SPEAKER = re.compile(rf"^([A-Z][0-9]?|Nam|Nữ|[{JAPANESE}]{{1,6}})\s*[:：]\s*")
NOT_SPEAKERS = {
    "例", "例文", "問", "問題", "質問", "答", "答え", "正解", "正答", "解答", "回答", "解説",
    "注", "注意", "ヒント", "メモ", "選択肢", "意味", "読み方",
}
BLOCK_ELEMENTS = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "section", "article", "header", "footer", "main",
    "aside", "nav", "center", "address", "figure", "figcaption", "dl", "dt", "dd", "form", "fieldset", "pre",
    "ul", "ol", "li", "hr", "img",
}
IGNORED_ELEMENTS = {"script", "style", "template", "head", "title", "meta", "link", "rt", "rp"}
VOID_ELEMENTS = {"br", "hr", "img", "meta", "link", "input", "wbr", "col", "area", "base", "embed", "source", "track"}


@dataclass(frozen=True)
class Block:
    text: str  # as NihonGo shows it: "F: すみません。" for a line of dialogue
    speaker: str | None  # F, M, 木山…; None for a paragraph
    body: str  # what is said: the text without the speaker label


def prepare(markup):
    """The markup as HTML with the readings and translations of the addon's notation taken out."""
    source = ESCAPED_MARKER.sub(lambda m: "<<" + m.group(1) + ">>", markup or "")

    def base(match):
        content = html.unescape(match.group(1)).strip()
        reading = READING.match(content)
        return html.escape((reading.group(1) if reading else content).strip(), quote=False)

    source = MARKER.sub(base, source)
    source = OTHER_TRANSLATION.sub("", source)
    source = TRANSLATION.sub("", source)
    return STRAY_LT.sub("&lt;", source)


def speaker_of(text):
    """(speaker, body) of a block's text, speaker None when the text does not open with a speaker label."""
    match = SPEAKER.match(text)
    if not match or match.group(1) in NOT_SPEAKERS or not text[match.end():].strip():
        return None, text
    return match.group(1), text[match.end():]


def _clean(text):
    return re.sub(r"[ \t\r\f\v ]+", " ", text.replace("​", "")).strip(" ")


class _Walker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texts = []  # (text, speaker, from a table)
        self.pending = []
        self.ignored = 0
        self.table = None  # rows of cells of the table being read; each cell is a list of strings
        self.depth = 0  # nested tables, read as text of the outer one

    def flush(self):
        text = "".join(self.pending)
        self.pending = []
        text = "\n".join(line for line in (_clean(part) for part in text.split("\n")) if line)
        if text:
            self.texts.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in IGNORED_ELEMENTS:
            if tag not in VOID_ELEMENTS:
                self.ignored += 1
            return
        if self.ignored:
            return
        if tag == "table":
            if self.table is not None:
                self.depth += 1
                return
            self.flush()
            self.table = []
        elif self.table is not None:
            if tag == "tr" and not self.depth:
                self.table.append([])
            elif tag in ("td", "th") and not self.depth and self.table:
                self.table[-1].append([])
            elif (tag == "br" or tag in BLOCK_ELEMENTS) and self._cell() is not None:
                self._cell().append("\n")
        elif tag == "br":
            self.pending.append("\n")
        elif tag in BLOCK_ELEMENTS:
            self.flush()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in IGNORED_ELEMENTS:
            self.ignored = max(0, self.ignored - 1)
            return
        if self.ignored:
            return
        if tag == "table":
            if self.depth:
                self.depth -= 1
                return
            rows, self.table = self.table or [], None
            self._dialogue_table(rows)
        elif self.table is not None:
            if tag in BLOCK_ELEMENTS and self._cell() is not None:
                self._cell().append("\n")
        elif tag in BLOCK_ELEMENTS:
            self.flush()

    def handle_data(self, data):
        if self.ignored:
            return
        if self.table is not None:
            if self._cell() is not None:
                self._cell().append(data.replace("\n", " "))
            return
        self.pending.append(data.replace("\n", " "))

    def _cell(self):
        if self.table and self.table[-1]:
            return self.table[-1][-1]
        return None

    def _dialogue_table(self, rows):
        cells = [[_clean(" ".join("".join(cell).split("\n"))) for cell in row] for row in rows if row]
        if not cells:
            return
        dialogue = all(
            len(row) == 3 and row[1] in (":", "：") and speaker_of(row[0] + ":" + (row[2] or "x"))[0] == row[0]
            for row in cells
        )
        if dialogue:
            self.texts.extend(f"{row[0]}: {row[2]}" for row in cells if row[2])


def blocks_of(markup):
    """The text blocks of a listening item's markup, in order."""
    walker = _Walker()
    walker.feed(prepare(markup))
    walker.close()
    walker.flush()
    blocks = []
    for text in walker.texts:
        speaker, body = speaker_of(text)
        shown = f"{speaker}: {body.strip()}" if speaker else text
        blocks.append(Block(shown, speaker, body.strip()))
    return blocks


def key(text):
    """How NihonGo compares a cue's text with a block's (AudioCues.key): NFKC, without spaces or zero-width marks."""
    normal = unicodedata.normalize("NFKC", text)
    return "".join(c for c in normal if not c.isspace() and c not in "​‌‍⁠﻿ ")
