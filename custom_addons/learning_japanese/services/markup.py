"""Markup helpers shared by the API: `<<漢字 - よみ>>` readings and `{{...}}` translations.

Odoo stores the markup inside Html fields with the markers escaped
(`&lt;&lt;人 - ひと&gt;&gt;`). The API shows and accepts them unescaped.
"""

import html
import re

from ..utils.furigana_helper import guess_reading, process_furigana

_RE_CODE_BLOCK = re.compile(r"<(pre|code)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_RE_MARKER = re.compile(r"<<([^<>]*)>>")
_RE_READING = re.compile(r"^(.+?)\s*-\s*(.+)$", re.DOTALL)
_RE_TRANSLATION = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_RE_TAG = re.compile(r"<[^>]*>")
_RE_BLOCK_END = re.compile(r"</p\s*>|</div\s*>|</li\s*>", re.IGNORECASE)
_RE_KANJI_RUN = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆ヶ]+")
_RE_JAPANESE = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")
_RE_KANA_READING = re.compile(r"^[぀-ヿー・\s]+$")
_RE_ESCAPED_LT_RUN = re.compile(r"(?:&lt;){2,}")


def _pair_from_the_right(run):
    """`&lt;` × n -> `<<` pairs, an odd one left first: it is a bracket before a marker."""
    count = len(run.group(0)) // len("&lt;")
    return "&lt;" * (count % 2) + "<<" * (count // 2)


def to_source(stored):
    """Stored Html value -> markup as people write it (markers unescaped).

    `&lt;&lt;&lt;質問 - しつもん&gt;&gt;&gt;` is `&lt;<<質問 - しつもん>>&gt;`: the `<` pairs
    are taken from the right and the `>` pairs from the left, as the converter reads them.
    """
    if not stored:
        return None
    return _RE_ESCAPED_LT_RUN.sub(_pair_from_the_right, str(stored)).replace("&gt;&gt;", ">>")


def to_stored(source):
    """Markup as people write it -> the value to store, with `<<` escaped as the Odoo editor saves it.

    Left as is, the Html sanitizer reads `<<kỳ nghỉ hè>>` as a `<kỳ>` tag and drops it with
    its text. `>` never opens a tag, so `>>` needs no escaping.
    """
    return source.replace("<<", "&lt;&lt;") if source else source


def same_markup(a, b):
    return (to_source(a) or "").strip() == (to_source(b) or "").strip()


def _text(fragment):
    """Text of an HTML fragment with markers kept: tags are stripped while markers are still escaped."""
    escaped = fragment.replace("<<", "&lt;&lt;").replace(">>", "&gt;&gt;")
    return html.unescape(_RE_TAG.sub(" ", escaped))


def plain_text(markup):
    """Visible text of the markup, without tags, readings or translations."""
    if not markup:
        return ""
    text = _text(_RE_CODE_BLOCK.sub(" ", to_source(markup)))
    text = _RE_MARKER.sub(lambda m: _RE_READING.sub(r"\1", m.group(1)), text)
    return _RE_TRANSLATION.sub(" ", text).strip()


def has_markup(markup):
    return bool(plain_text(markup))


def render(markup):
    """(hover HTML, ruby HTML), exactly as Odoo produces them when the markup is saved."""
    return process_furigana(markup or "")


def analyze(markup):
    """Stats and problems of a markup string; see MarkupIssue in openapi.yaml."""
    source = _RE_CODE_BLOCK.sub(" ", to_source(markup) or "")

    # Paragraphs holding Japanese; a translation-only paragraph counts for the one before it.
    blocks, translation_counts = [], []
    for fragment in _RE_BLOCK_END.split(source):
        text = _text(fragment)
        found = len(_RE_TRANSLATION.findall(text))
        if _RE_JAPANESE.search(_RE_TRANSLATION.sub(" ", text)):
            blocks.append(text)
            translation_counts.append(found)
        elif found and translation_counts:
            translation_counts[-1] += found

    issues = []
    stats = {"blocks": len(blocks), "markers": 0, "explicit_readings": 0, "auto_readings": 0,
             "translations": sum(translation_counts)}
    seen_auto = set()
    for index, text in enumerate(blocks):
        text = _RE_TRANSLATION.sub(" ", text)
        if "{{" in text or "}}" in text:
            issues.append(_issue("unbalanced_translation", "Thiếu {{ hoặc }} trong đoạn.", block=index))

        for raw in _RE_MARKER.findall(text):
            stats["markers"] += 1
            content = raw.strip()
            match = _RE_READING.match(content)
            if not content or (match and not match.group(1).strip()):
                issues.append(_issue("empty_marker", "Marker rỗng.", text=f"<<{raw}>>", block=index))
            elif match:
                stats["explicit_readings"] += 1
                reading = match.group(2).strip()
                if not _RE_KANA_READING.match(reading):
                    issues.append(_issue(
                        "reading_not_kana", "Cách đọc phải là kana.", text=match.group(1).strip(),
                        reading=reading, block=index,
                    ))
            else:
                stats["auto_readings"] += 1
                if content not in seen_auto:
                    seen_auto.add(content)
                    issues.append(_issue(
                        "auto_reading", "Chưa ghi cách đọc; pykakasi tự đoán, cần kiểm tra.",
                        text=content, reading=guess_reading(content), block=index,
                    ))

        rest = _RE_MARKER.sub(" ", text)
        if "<<" in rest or ">>" in rest:
            issues.append(_issue("unbalanced_marker", "Thiếu << hoặc >> trong đoạn.", block=index))
        for run in _RE_KANJI_RUN.findall(rest):
            issues.append(_issue(
                "kanji_without_reading", "Kanji nằm ngoài <<>> nên không có furigana.", text=run, block=index,
            ))

    if stats["translations"]:
        for index, count in enumerate(translation_counts):
            if not count:
                issues.append(_issue("missing_translation", "Đoạn chưa có bản dịch {{...}}.", block=index))
    return {"stats": stats, "issues": issues}


def _issue(code, message, **extra):
    return {"code": code, "message": message, **extra}
