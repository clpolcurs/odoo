"""Propose <<漢字 - よみ>> markers for the kanji the learning_japanese markup left without a reading.

The markup is HTML where a word written with kanji is <<漢字 - よみ>> (learning_japanese services/markup.py).
Kanji outside every marker are what its analyze() reports as kanji_without_reading. For each of them this module
takes the Sudachi word around it (split mode C, the whole paragraph as context, marked words included) and
proposes markers in the house style, the kanji only with their own reading: <<言 - い>>って, <<食 - た>>べる,
<<引 - ひ>>っ<<越 - こ>>し. A number in front of a counter goes into the marker, because the reading of the
counter changes with the number: <<3日 - みっか>>, <<10分 - じゅっぷん>>, <<1人 - ひとり>>.

Nothing inside a tag, an existing marker, a {{translation}} or a <pre>/<code> block is touched, and a marker only
wraps characters that are plain text of the markup, so the visible text stays the same.
"""

import html
import re
from dataclasses import dataclass, field
from itertools import pairwise

from sudachipy import Dictionary, SplitMode

DICTIONARY = Dictionary(dict="core")
TOKENIZER = DICTIONARY.tokenizer(mode=SplitMode.C)
SHORT_TOKENIZER = DICTIONARY.tokenizer(mode=SplitMode.A)

KANJI = "㐀-䶿一-鿿豈-﫿々〆ヶ"  # the kanji of analyze() (_RE_KANJI_RUN)
RE_KANJI = re.compile(f"[{KANJI}]")
RE_KANJI_PARTS = re.compile(f"[{KANJI}]+|[^{KANJI}]+")
RE_HIRAGANA = re.compile(r"^[ぁ-ゖー]+$")
RE_KANA = re.compile(r"[ぁ-ゖァ-ヺー]")
RE_KATAKANA = re.compile(r"[ァ-ヺー]")
RE_KANA_OR_KANJI = re.compile(f"[ぁ-ゖァ-ヺー{KANJI}]")
RE_MARKER = re.compile(r"<<([^<>]*)>>")
RE_READING = re.compile(r"^(.+?)\s*-\s*(.+)$", re.DOTALL)
RE_EXCLUDED = re.compile(r"<(pre|code)\b[^>]*>.*?</\1>|\{\{.*?\}\}", re.DOTALL | re.IGNORECASE)
RE_TAG = re.compile(r"<[^<>]*>")
RE_BLOCK_TAG = re.compile(r"</?(?:p|div|li|ul|ol|br|h[1-6]|td|th|tr|table|blockquote|hr)\b", re.IGNORECASE)
RE_ENTITY = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z]+);")
INVISIBLE = "​‌‍⁠﻿"


def hiragana(text):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


# ---------- the text of the markup, with the offset of every character ----------


@dataclass
class Paragraph:
    text: str
    sources: list  # markup offset of each character, None when it is not plain text there (entity, marker)
    marked: list  # the character belongs to an existing marker
    broken: bool = False  # a << that is not a marker: no proposal in this paragraph
    markers: list = field(default_factory=list)  # (start, end, explicit reading or None) of the existing markers


def paragraphs(markup):
    """The paragraphs of the markup as Sudachi should read them: tags dropped, markers as their words."""
    out, current = [], Paragraph("", [], [])

    def flush():
        nonlocal current
        if current.text:
            out.append(current)
        current = Paragraph("", [], [])

    def add(char, source, marked=False):
        current.text += char
        current.sources.append(source)
        current.marked.append(marked)

    excluded = {m.start(): m.end() for m in RE_EXCLUDED.finditer(markup or "")}
    i, n = 0, len(markup or "")
    while i < n:
        if i in excluded:
            flush()
            i = excluded[i]
            continue
        char = markup[i]
        if char == "<":
            marker = RE_MARKER.match(markup, i) if markup.startswith("<<", i) else None
            if marker:
                content = marker.group(1)
                reading = RE_READING.match(content)
                base = (reading.group(1) if reading else content).strip()
                explicit = hiragana(reading.group(2).strip()) if reading else None
                current.markers.append((len(current.text), len(current.text) + len(base), explicit))
                for c in base:
                    add(c, None, marked=True)
                i = marker.end()
                continue
            tag = RE_TAG.match(markup, i)
            if tag and not markup.startswith("<<", i):
                if RE_BLOCK_TAG.match(tag.group(0)):
                    flush()
                i = tag.end()
                continue
            current.broken = True
        elif char == "&" and (entity := RE_ENTITY.match(markup, i)):
            add(html.unescape(entity.group(0)).replace("\xa0", " "), None)
            i = entity.end()
            continue
        if char not in INVISIBLE:
            add(char, i)
        i += 1
    flush()
    return out


# ---------- readings of numbers and counters ----------

ONES = ["", "いち", "に", "さん", "よん", "ご", "ろく", "なな", "はち", "きゅう"]
KANJI_DIGITS = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
KANJI_UNITS = {"十": 10, "百": 100, "千": 1000}
BIG_UNITS = {"万": 10**4, "億": 10**8, "兆": 10**12}


def _below_10000(n):
    """Pieces of the reading of 1..9999; units stand alone so that a counter can change them (さん + じゅう + っ)."""
    parts = []
    thousands, n = divmod(n, 1000)
    if thousands:
        parts += {1: ["せん"], 3: ["さん", "ぜん"], 8: ["はっ", "せん"]}.get(thousands, [ONES[thousands], "せん"])
    hundreds, n = divmod(n, 100)
    if hundreds:
        parts += {1: ["ひゃく"], 3: ["さん", "びゃく"], 6: ["ろっ", "ぴゃく"], 8: ["はっ", "ぴゃく"]}.get(
            hundreds, [ONES[hundreds], "ひゃく"]
        )
    tens, ones = divmod(n, 10)
    if tens:
        parts += ["じゅう"] if tens == 1 else [ONES[tens], "じゅう"]
    if ones:
        parts.append(ONES[ones])
    return parts


def number_parts(n):
    """The reading of n in pieces, the last one being what a counter can change (いち → いっ)."""
    if n == 0:
        return ["ぜろ"]
    parts = []
    for unit, word in ((10**12, "ちょう"), (10**8, "おく"), (10**4, "まん")):
        count, n = divmod(n, unit)
        if count:
            parts += [*_below_10000(count), word]
    return parts + _below_10000(n)


def parse_number(text):
    """123, １２３, 1,000, 三, 二十五, 百, 3万, 1億2000万 → int; None for anything else (1.5, 三四)."""
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789")).replace(",", "").replace("，", "")
    if not text:
        return None
    total, section, current, i = 0, 0, None, 0
    while i < len(text):
        c = text[i]
        if c.isdigit() or c in KANJI_DIGITS:
            if current is not None:
                return None  # 三四: two numbers in a row
            j = i + 1
            while c.isdigit() and j < len(text) and text[j].isdigit():
                j += 1
            current = int(text[i:j]) if c.isdigit() else KANJI_DIGITS[c]
            i = j
            continue
        if c in KANJI_UNITS:
            section += (1 if current is None else current) * KANJI_UNITS[c]
        elif c in BIG_UNITS:
            total += (section + (current or 0) or 1) * BIG_UNITS[c]
            section = 0
        else:
            return None
        current = None
        i += 1
    return total + section + (current or 0)


GEMINATE = {"いち": "いっ", "ろく": "ろっ", "はち": "はっ", "じゅう": "じゅっ", "ひゃく": "ひゃっ", "びゃく": "びゃっ",
            "ぴゃく": "ぴゃっ"}  # fmt: skip
# Counters by how the number before them changes: か-row ones double the last sound of 1, 6, 8, 10 and 100
# (いっかい), さ- and た-row ones that of 1, 8 and 10 (いっさい, いってん), は-row ones that of 1, 6, 8, 10 and 100
# and become ぱ-row (いっぽん), after さん they are voiced (さんぼん) or ぱ-row (さんぷん) as the second value says.
K_ROW = {
    "回": "かい", "回目": "かいめ", "個": "こ", "ヶ月": "かげつ", "か月": "かげつ", "カ月": "かげつ",
    "ヵ月": "かげつ", "箇月": "かげつ", "階": "かい", "階建て": "かいだて", "軒": "けん", "件": "けん",
    "曲": "きょく", "課": "か", "か国": "かこく", "ヶ国": "かこく", "カ国": "かこく", "か所": "かしょ",
    "ヶ所": "かしょ", "カ所": "かしょ", "箇所": "かしょ",
}  # fmt: skip
S_ROW = {
    "歳": "さい", "才": "さい", "冊": "さつ", "週間": "しゅうかん", "週": "しゅう", "足": "そく", "社": "しゃ",
    "席": "せき", "世紀": "せいき", "点": "てん", "頭": "とう", "等": "とう", "通": "つう", "着": "ちゃく",
    "丁目": "ちょうめ",
}  # fmt: skip
H_ROW = {"本": ("ほん", "voiced"), "匹": ("ひき", "voiced"), "杯": ("はい", "voiced"), "分": ("ふん", "p"),
         "分間": ("ふんかん", "p"), "泊": ("はく", "p"), "歩": ("ほ", "p"), "発": ("はつ", "p")}  # fmt: skip
VOICED_AFTER_THREE = {"階", "階建て", "軒", "足"}  # さんがい, さんげん, さんぞく
PLAIN = {
    "枚": "まい", "台": "だい", "度": "ど", "度目": "どめ", "円": "えん", "番": "ばん", "番目": "ばんめ",
    "番線": "ばんせん", "名": "めい", "秒": "びょう", "倍": "ばい", "位": "い", "号": "ごう", "割": "わり",
    "代": "だい", "部": "ぶ", "年": "ねん", "年間": "ねんかん", "年生": "ねんせい", "年前": "ねんまえ",
    "年後": "ねんご", "年代": "ねんだい", "時": "じ", "時間": "じかん", "時半": "じはん", "時頃": "じごろ",
    "月": "がつ", "人": "にん", "人前": "にんまえ",
}  # fmt: skip
YO_BEFORE = {"円", "年", "年間", "年生", "年前", "年後", "年代", "時", "時間", "時半", "時頃", "人", "人前"}  # よじ
HOURS = {"時", "時間", "時半", "時頃"}  # しちじ, くじ
DAYS = {1: "ついたち", 2: "ふつか", 3: "みっか", 4: "よっか", 5: "いつか", 6: "むいか", 7: "なのか", 8: "ようか",
        9: "ここのか", 10: "とおか", 14: "じゅうよっか", 20: "はつか", 24: "にじゅうよっか"}  # fmt: skip
VOICE = str.maketrans("かきくけこさしすせそたちつてとはひふへほ", "がぎぐげござじずぜぞだぢづでどばびぶべぼ")
HALF_VOICE = str.maketrans("はひふへほ", "ぱぴぷぺぽ")
COUNTER_WORDS = set(K_ROW) | set(S_ROW) | set(H_ROW) | set(PLAIN) | {"日", "日間", "日目", "人目"}


def counter_reading(n, counter):
    """(reading of the number n with the counter, doubt), or None when the counter is not one we know."""
    if counter in ("日", "日間", "日目"):
        if n == 1:
            reading = {"日": "ついたち", "日間": "いちにちかん", "日目": "いちにちめ"}[counter]
            return reading, "1日: ついたち (ngày mùng 1) hay いちにち (một ngày)" if counter == "日" else ""
        day = DAYS.get(n)
        if day is None:
            parts = number_parts(n)
            day = "".join(parts[:-1]) + {"なな": "しち", "きゅう": "く"}.get(parts[-1], parts[-1]) + "にち"
        return day + {"日": "", "日間": "かん", "日目": "め"}[counter], ""
    if counter in ("人", "人目") and n in (1, 2):
        return ("ひとり", "ふたり")[n - 1] + ("め" if counter == "人目" else ""), ""
    if counter == "人目":
        return "".join(number_parts(n)) + "にんめ", ""
    if counter in ("歳", "才") and n == 20:
        return "はたち", "20歳: はたち hay にじゅっさい"
    parts = number_parts(n)
    last = parts[-1]
    if counter in YO_BEFORE and last == "よん":
        last = "よ"
    if counter in HOURS:
        last = {"なな": "しち", "きゅう": "く"}.get(last, last)
    if counter == "月":
        last = {"よん": "し", "なな": "しち", "きゅう": "く"}.get(last, last)
    if counter in K_ROW or counter in S_ROW:
        reading = K_ROW.get(counter) or S_ROW[counter]
        doubles = set(GEMINATE) if counter in K_ROW else {"いち", "はち", "じゅう"}
        if last in doubles:
            last = GEMINATE[last]
        elif last == "さん" and counter in VOICED_AFTER_THREE:
            reading = reading[0].translate(VOICE) + reading[1:]
    elif counter in H_ROW:
        reading, after_three = H_ROW[counter]
        if last in GEMINATE:
            last, reading = GEMINATE[last], reading[0].translate(HALF_VOICE) + reading[1:]
        elif last in ("さん", "せん", "まん") or (last == "よん" and counter in ("分", "分間")):  # さんぼん, まんぼん
            table = VOICE if after_three == "voiced" else HALF_VOICE
            reading = reading[0].translate(table) + reading[1:]
    elif counter in PLAIN:
        reading = PLAIN[counter]
    else:
        return None
    return "".join(parts[:-1]) + last + reading, ""


# ---------- proposals ----------


@dataclass
class Marker:
    start: int  # markup offsets of the characters the marker wraps
    end: int
    text: str
    reading: str
    word: str  # the Sudachi word it comes from (dictionary form), to group the review
    doubt: str = ""  # why a person should check this reading, "" when Sudachi and the rules are enough
    note: str = ""  # how the reading was found when it is not Sudachi's: a counter, the readings of the content
    context: str = ""


@dataclass
class Missing:
    text: str  # kanji left without a proposal
    why: str
    context: str = ""


class Fix:
    """An edit of the text itself: a typo replaced instead of read (一 typed for the long vowel ー: 助けて一, ノ一残業),
    or the brackets of a marker without reading that new markers replace (why == BRACKETS)."""

    def __init__(self, start, end, text, replacement, why, context=""):
        self.start, self.end, self.text, self.replacement = start, end, text, replacement
        self.why, self.context = why, context


@dataclass
class Proposal:
    markers: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    fixes: list = field(default_factory=list)
    replaced: list = field(default_factory=list)  # (start, end, text): markers without reading propose_auto replaces


BRACKETS = "ngoặc của dấu không ghi cách đọc"


def _around(markup, match, width=40):
    return re.sub(r"\s+", " ", RE_TAG.sub("", markup[max(0, match.start() - width) : match.end() + width]))


NAN_BEFORE = ("で", "だ", "です", "の", "と", "て", "ど", "なら", "じゃ")


def nani_or_nan(following):
    """(reading, doubt) of 何 from the text after it; Sudachi always says なん."""
    if following.startswith(tuple(COUNTER_WORDS)) or following.startswith(("曜日", "種類", "通り", "日")):
        return "なん", ""
    if not following.startswith(NAN_BEFORE):
        return "なに", ""
    if following.startswith("で") and not following.startswith(("です", "でしょう", "でも")):
        return "なん", "何で: なんで (tại sao) hay なにで (bằng gì)"
    return "なん", ""


VARIANTS = {("言", "ゆ"): "い"}  # 言う: Sudachi gives ゆう as often as いう

# Sudachi words whose reading depends on what the sentence means; the others it reads right from their part of
# speech, inflection and neighbours (人: ひと / 3人: にん, 来ます: き / 来ない: こ, 調査を行った: おこなっ / 学校へ
# 行った: いっ, 気に入って, 雨が降り出した: ふり / バスを降りた: おり).
AMBIGUOUS = {
    "方": "ほう (phía, hơn) hay かた (người, cách làm)",
    "他": "ほか hay た", "後": "あと / ご / のち / うしろ", "間": "あいだ / ま / かん", "皆": "みな hay みんな",
    "一日": "いちにち hay ついたち", "十分": "じゅうぶん (đủ) hay じゅっぷん (10 phút)",
    "一時": "いちじ hay いっとき", "何時": "なんじ hay いつ", "今日": "きょう hay こんにち (ngày nay)",
    "人気": "にんき hay ひとけ", "大家": "おおや hay たいか", "市場": "いちば hay しじょう",
    "生": "なま / せい / き", "角": "かど / かく / つの", "金": "かね hay きん", "床": "ゆか hay とこ",
    "寒気": "さむけ hay かんき", "目下": "もっか hay めした", "辛い": "からい (cay) hay つらい (khổ)",
    "辛く": "からく hay つらく", "辛かっ": "からかっ hay つらかっ", "開い": "あい hay ひらい",
    "開く": "あく hay ひらく", "開き": "あき hay ひらき", "開か": "あか hay ひらか",
    "空い": "あい (trống) hay すい (vắng)", "空く": "あく hay すく", "空き": "あき hay すき",
    "止め": "とめ hay やめ", "止める": "とめる hay やめる", "抱い": "だい hay いだい", "抱く": "だく hay いだく",
    "弾い": "ひい hay はじい", "弾く": "ひく hay はじく", "何時ごろ": "なんじごろ hay いつごろ",
    "何時頃": "なんじごろ hay いつごろ", "問": "とい hay もん (nhãn câu hỏi)",
}  # fmt: skip


def context_of(text, start, end, width=18):
    left, right = text[max(0, start - width) : start], text[end : end + width]
    return (left + "【" + text[start:end] + "】" + right).replace("\n", " ")


def align(surface, reading):
    """[(offset, length, reading)] for each kanji run of the surface, or None when its kana are not in the reading."""
    parts = RE_KANJI_PARTS.findall(surface)
    pattern = "".join("(.+?)" if RE_KANJI.match(p) else re.escape(hiragana(p)) for p in parts)
    match = re.fullmatch(pattern, reading)
    if not match:
        return None
    out, offset, group = [], 0, 1
    for part in parts:
        if RE_KANJI.match(part):
            out.append((offset, len(part), match.group(group)))
            group += 1
        offset += len(part)
    return out


RE_KANJI_NUMBER_WORD = re.compile("([〇一二三四五六七八九十百千万億兆]+)(.+)")
DIGITS = "0123456789０１２３４５６７８９"


class Proposer:
    """Proposals for the kanji of one markup; known is {kanji: Counter(reading)} of the explicit readings of the
    published content, used to confirm or question what Sudachi says."""

    def __init__(self, known=None):
        self.known = known or {}

    def propose(self, markup):
        out = Proposal()
        for paragraph in paragraphs(markup):
            self._paragraph(paragraph, out)
        return out

    def propose_auto(self, markup):
        """Readings for the markers written without one (<<状態>>, <<強く>>, 22<<歳>>): their brackets go (fixes) and
        their kanji are read in context like unmarked ones, in the house style: <<強 - つよ>>く,
        <<22歳 - にじゅうにさい>>. The new markers are placed in the markup the fixes leave; out.replaced has where
        the old markers' words are in it, out.missing the markers kept: a new marker would not cover all of their
        kanji, or they lie in a translation or a code block."""
        excluded = [m.span() for m in RE_EXCLUDED.finditer(markup)]
        out, candidates = Proposal(), []
        for m in RE_MARKER.finditer(markup):
            if RE_KANJI.search(m.group(1)) and not RE_READING.match(m.group(1)):
                if any(a <= m.start() < b for a, b in excluded):
                    out.missing.append(Missing(m.group(1), "nằm trong bản dịch hoặc khối code", _around(markup, m)))
                else:
                    candidates.append(m)
        while True:  # a marker that cannot be replaced keeps its brackets, which moves what follows: propose again
            stripped, spans = markup, []
            for m in candidates:
                start = m.start() - 4 * len(spans)
                stripped = stripped[:start] + m.group(1) + stripped[start + len(m.group(0)) :]
                spans.append((start, start + len(m.group(1))))
            found = self.propose(stripped).markers
            kept = []
            for i, (start, end) in enumerate(spans):
                covered = {j for k in found if k.start < end and k.end > start for j in range(k.start, k.end)}
                if any(RE_KANJI.match(stripped[j]) and j not in covered for j in range(start, end)):
                    kept.append(i)
            if not kept:
                break
            out.missing += [Missing(candidates[i].group(1), "không tách được cách đọc", _around(markup, candidates[i]))
                            for i in kept]  # fmt: skip
            candidates = [m for i, m in enumerate(candidates) if i not in kept]
        out.markers = [k for k in found if any(k.start < end and k.end > start for start, end in spans)]
        out.replaced = [(start, end, m.group(1)) for (start, end), m in zip(spans, candidates, strict=True)]
        for m in candidates:
            out.fixes += [
                Fix(m.start(), m.start() + 2, "<<", "", BRACKETS),
                Fix(m.end() - 2, m.end(), ">>", "", BRACKETS),
            ]
        return out

    @staticmethod
    def _unmarked(paragraph, start, end):
        return any(RE_KANJI.match(paragraph.text[j]) and not paragraph.marked[j] for j in range(start, end))

    @staticmethod
    def _span(paragraph, start, end):
        """Markup offsets of text[start:end], or None when it is not one plain run of the markup."""
        sources = paragraph.sources[start:end]
        if None in sources or any(b != a + 1 for a, b in pairwise(sources)):
            return None
        return sources[0], sources[-1] + 1

    def _paragraph(self, paragraph, out):
        text = paragraph.text
        if not self._unmarked(paragraph, 0, len(text)):
            return
        if paragraph.broken:
            runs = re.finditer(f"[{KANJI}]+", text)
            out.missing += [Missing(m.group(0), "đoạn có dấu << hỏng", text[:40]) for m in runs]
            return
        words = list(TOKENIZER.tokenize(text))
        short_words = None
        k = 0
        while k < len(words):
            word = words[k]
            start, end = word.begin(), word.end()
            k += 1
            if not self._unmarked(paragraph, start, end):
                continue
            if any(paragraph.marked[start:end]):  # part of the word is marked already (昼ご<<飯>>, 2<<年>>間)
                if self._word(paragraph, word, out, partly=True):
                    continue
                if short_words is None:  # its kana do not line up with its reading: take its short units
                    short_words = list(SHORT_TOKENIZER.tokenize(text))
                for short in short_words:
                    s, e = short.begin(), short.end()
                    if s >= start and e <= end and self._unmarked(paragraph, s, e):
                        if any(paragraph.marked[s:e]):
                            out.missing.append(Missing(text[s:e], "dính vào dấu có sẵn", context_of(text, s, e)))
                        else:
                            self._word(paragraph, short, out)
                continue
            if word.part_of_speech()[1] == "数詞":  # 三 + 人, 二十 + 五 + 歳, 3 + 万 + 円, 3万 + 円
                last = k
                while last < len(words) and words[last].part_of_speech()[1] == "数詞":
                    last += 1
                counter = words[last] if last < len(words) else None
                begin = self._digits_start(paragraph, start)
                value = parse_number(text[begin : words[last - 1].end()])
                counter_word = counter.surface() if counter is not None else ""
                split = RE_KANJI_NUMBER_WORD.fullmatch(counter_word)
                if split and split.group(2) in COUNTER_WORDS and parse_number(split.group(1)) is not None:
                    value = parse_number(text[begin : words[last - 1].end()] + split.group(1))  # 三 + 十分: 三十 + 分
                    counter_word = split.group(2)
                if counter is not None and value is not None and not any(paragraph.marked[begin : counter.end()]):
                    counted = counter_reading(value, counter_word)
                    if counted is not None:
                        self._number(paragraph, begin, counter.end(), counted, counter_word, out)
                        k = last + 1
                        continue
                number_end = words[last - 1].end()
                if (
                    value is not None
                    and RE_KANJI.search(text[begin:number_end])
                    and number_end - begin > 1  # 一 of 一つ is Sudachi's: ひと
                    and not any(paragraph.marked[begin:number_end])
                ):  # 16万, 二十: Sudachi reads the digits one by one
                    self._number(paragraph, begin, number_end, ("".join(number_parts(value)), ""), "", out)
                    k = last
                    continue
            if word.surface() in COUNTER_WORDS and (number := self._digits_before(paragraph, start)) is not None:
                counted = counter_reading(number[1], word.surface())
                if counted is not None:
                    self._number(paragraph, number[0], end, counted, word.surface(), out)
                    continue
            self._word(paragraph, word, out)

    @staticmethod
    def _digits_start(paragraph, start):
        """Where the digits written right before text[start] begin (start when there are none)."""
        text, begin = paragraph.text, start
        while begin > 0 and (text[begin - 1] in DIGITS or text[begin - 1] in ",，") and not paragraph.marked[begin - 1]:
            begin -= 1
        while begin < start and text[begin] in ",，":
            begin += 1
        return start if begin > 0 and text[begin - 1] in ".．" else begin

    def _digits_before(self, paragraph, start):
        """(offset, value) of the number in digits right before text[start], or None."""
        begin = self._digits_start(paragraph, start)
        value = parse_number(paragraph.text[begin:start]) if begin < start else None
        return None if value is None else (begin, value)

    def _number(self, paragraph, start, end, counted, counter, out):
        text = paragraph.text
        span = self._span(paragraph, start, end)
        if span is None:
            out.missing.append(Missing(text[start:end], "số và đơn vị bị thẻ HTML cắt", context_of(text, start, end)))
            return
        reading, doubt = counted
        if reading == "ついたち" and not text[:start].endswith("月"):  # 1日に3回: いちにち, 1月1日: ついたち
            reading = "いちにち"
        context = context_of(text, start, end)
        out.markers.append(Marker(*span, text[start:end], reading, counter, doubt, "số đếm", context))

    def _word(self, paragraph, word, out, partly=False):
        """Markers for the unmarked kanji of the word; partly: some are marked, and False is returned when the
        word cannot be split along its reading."""
        text = paragraph.text
        start, end = word.begin(), word.end()
        surface, pos = word.surface(), word.part_of_speech()
        context = context_of(text, start, end)
        reading, doubt = hiragana(word.reading_form()), ""
        if surface == "何":
            reading, doubt = nani_or_nan(text[end : end + 4])
        elif surface == "今" and pos[0] == "接頭辞":  # 今電車が止まって: いま, not こん of 今世紀
            reading, doubt = "いま", "いま hay こん (今 + danh từ)"
        elif surface == "一" and start and RE_KANA.match(text[start - 1]):
            after = text[end : end + 1]
            if RE_KATAKANA.match(text[start - 1]) or not after or not RE_KANA_OR_KANJI.match(after):
                span = self._span(paragraph, start, end)
                if span is not None:  # ノ一残業, 助けて一」: the long vowel ー, typed as the kanji 一
                    out.fixes.append(Fix(*span, "一", "ー", "dấu kéo dài ー gõ nhầm thành 一", context))
                    return True
        elif surface == "何時":  # 何時に着く, 何時まで: なんじ; 何時でも: いつ (Sudachi: いつ, なんどき)
            reading = "なんじ" if text[end : end + 2].startswith(("に", "から", "まで", "半", "間")) else "いつ"
        elif surface == "他" and text[end : end + 1] in ("に", "の", "は", "も"):  # 他にも: ほか (Sudachi: た)
            reading, doubt = "ほか", "-"
        elif surface == "今日":  # Sudachi says こんにち before a noun (今日会議がある): it is きょう but in 今日では
            formal = re.match(r"では|の(?:社会|世界|日本|時代)", text[end : end + 3])
            reading, doubt = ("こんにち", AMBIGUOUS["今日"]) if formal else ("きょう", "-")  # 今日では: nowadays
        elif surface == "皆" and text[end : end + 2].startswith(("さん", "様", "さま")):
            reading, doubt = "みな", "-"
        elif surface == "方" and reading == "ほう" and text[end : end + 1] not in ("が", "へ"):
            reading = "かた"  # ご希望の方は, 一般の方も: a person; ほう stays for こちらの方が (better), 駅の方へ
        elif surface == "後" and text[:start].endswith(("この", "その", "あの")):
            # 男の人はこの後、何をしますか: このあと (Sudachi: ご); その後 can also be そのご
            reading, doubt = "あと", AMBIGUOUS["後"] if not text[:start].endswith("この") else "-"
        elif surface == "家" and reading in ("や", "か", "け") and text[end : end + 1] in "でにへをがはの":
            reading = "いえ"  # 明日家でパーティー: Sudachi takes it for the や of 八百屋
        elif (
            pos[1] == "固有名詞"
            and text[end:].lstrip(" \u3000")[:1] in tuple("へをにでがはのもと")  # 宇宙へ, not 本田さん
            and (common := self._common_reading(surface)) not in (None, reading)
        ):
            reading, doubt = common, "Sudachi coi là tên riêng"  # 宇宙へ行ける: うちゅう, not そら
        number = RE_KANJI_NUMBER_WORD.fullmatch(surface)
        if number and surface not in AMBIGUOUS and number.group(2) in COUNTER_WORDS - {"日", "日間", "日目"}:
            begin = self._digits_start(paragraph, start)  # 3 + 万円
            value = parse_number(text[begin:start] + number.group(1))
            counted = counter_reading(value, number.group(2)) if value else None  # 一回: Sudachi いちかい
            if counted is not None:
                self._number(paragraph, begin, end, counted, surface, out)
                return
        if not RE_HIRAGANA.match(reading):
            out.missing.append(Missing(surface, "Sudachi không biết cách đọc", context))
            return
        doubt = "" if doubt == "-" else doubt or AMBIGUOUS.get(surface, "")  # "-": a rule settled it
        core = re.split(r"[（(]", surface)[0] or surface  # 上（に）, 以上(は): the brackets are not read
        pieces = align(core, reading)
        if pieces is None:
            if partly:
                return False
            pieces = [(0, len(core), reading)]  # お土産 → おみやげ: the whole word
        name = pos[1] == "固有名詞" and pos[2] in ("人名", "地名")
        markers, missing = [], []
        for offset, length, piece in pieces:
            s, e = start + offset, start + offset + length
            if all(paragraph.marked[s:e]):
                continue
            if any(paragraph.marked[s:e]):
                rest = self._rest_of(paragraph, s, e, piece)
                if rest is None:
                    missing.append(Missing(text[s:e], "dính vào dấu có sẵn", context))
                    continue
                s, e, piece = rest
            span = self._span(paragraph, s, e)
            if span is None:
                missing.append(Missing(text[s:e], "chữ bị thẻ HTML cắt", context))
                continue
            # a noun on its own (私, 日本), not 好 of 世話好き, 店 of 駅前店 or 落 of 落着かない
            whole = e - s == len(surface) and pos[0] in ("名詞", "代名詞", "形状詞")
            final, why, note = self._judge(text[s:e], VARIANTS.get((text[s:e], piece), piece), doubt, name, whole)
            markers.append(Marker(*span, text[s:e], final, word.dictionary_form(), why, note, context))
        if partly and missing:
            return False  # <<日本>>語: the marker has no reading to take off, the short units will do
        out.markers += markers
        out.missing += missing
        return True

    @staticmethod
    def _common_reading(surface):
        """The reading of the surface as a common noun when Sudachi also has it as one (宇宙: うちゅう)."""
        readings = {
            hiragana(m.reading_form()) for m in DICTIONARY.lookup(surface) if m.part_of_speech()[1] == "普通名詞"
        }
        return readings.pop() if len(readings) == 1 else None

    @staticmethod
    def _rest_of(paragraph, start, end, reading):
        """(start, end, reading) of the unmarked kanji of the run text[start:end] whose other end is one existing
        marker with an explicit reading: 2<<年 - ねん>>間 → 間 = かん, 病<<気 - き>> → 病 = びょう."""
        ids = {i for i, (s, e, _) in enumerate(paragraph.markers) if s < end and e > start}
        if len(ids) != 1:
            return None
        s, e, known = paragraph.markers[ids.pop()]
        if known is None or s < start or e > end or len(reading) <= len(known):
            return None
        if s == start and reading.startswith(known) and not any(paragraph.marked[e:end]):
            return e, end, reading[len(known) :]
        if e == end and reading.endswith(known) and not any(paragraph.marked[start:s]):
            return start, s, reading[: -len(known)]
        return None

    def _judge(self, piece, reading, doubt, name, whole):
        """(reading, doubt, note) once the explicit readings of the same kanji in the content are known: Sudachi
        reads 私 わたくし and 日本 にっぽん on their own, the books write わたし and にほん. Only a whole word takes
        the reading of the content; the kanji of a longer word (好 of 世話好き: ず) is left for a person."""
        seen = self.known.get(piece)
        if seen and reading not in seen:
            top, count = seen.most_common(1)[0]
            if whole and count >= 3 and count >= 0.8 * sum(seen.values()):
                return top, doubt, f"theo cách ghi trong nội dung (Sudachi đọc {reading})"
            return reading, doubt or "nội dung đang ghi " + " / ".join(r for r, _ in seen.most_common(3)), ""
        if name and not seen:
            return reading, doubt or "tên riêng", ""
        return reading, doubt, ""


def apply(markup, markers, fixes=()):
    """The markup with the fixes made (typos, brackets taken away), then the markers inserted where the fixes leave
    their text; none of them may overlap."""
    for fix in sorted(fixes, key=lambda f: f.start, reverse=True):
        assert markup[fix.start : fix.end] == fix.text, (fix.start, fix.text, markup[fix.start : fix.end])
        markup = markup[: fix.start] + fix.replacement + markup[fix.end :]
    for m in sorted(markers, key=lambda m: m.start, reverse=True):
        assert markup[m.start : m.end] == m.text, (m.start, m.text, markup[m.start : m.end])
        markup = markup[: m.start] + f"<<{m.text} - {m.reading}>>" + markup[m.end :]
    return markup


def known_readings(markups):
    """{kanji: Counter(reading)} of the explicit <<漢字 - よみ>> markers of the markups."""
    from collections import Counter, defaultdict

    known = defaultdict(Counter)
    for markup in markups:
        for content in RE_MARKER.findall(markup or ""):
            match = RE_READING.match(content)
            if match:
                text, reading = match.group(1).strip(), hiragana(match.group(2).strip().replace(" ", ""))
                if RE_HIRAGANA.match(reading) and RE_KANJI.search(text):
                    known[text][reading] += 1
    return dict(known)
