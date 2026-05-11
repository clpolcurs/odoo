import html
import re
import logging
from pykakasi import kakasi

_logger = logging.getLogger(__name__)

# ── Module-Level Singletons ────────────────────────────────────────────────────
_KKS = kakasi()

# Compiled regular expressions
_RE_KANJI_MATCH = re.compile(r"<<([^<>]+)>>")
_RE_VIET_KEEP = re.compile(r"\{\{(.+?)\}\}", re.DOTALL)
_RE_VIET_REMOVE = re.compile(r"(?:<br\s*/?>)?\s*\{\{.+?\}\}", re.DOTALL)
_RE_MANUAL_READING = re.compile(r"^(.+?)\s*-\s*(.+)$")  # Matches "Kanji - furigana"


# ── Helper Functions ───────────────────────────────────────────────────────────

def _strip_vietnamese(text: str, keep_content: bool) -> str:
    if keep_content:
        return _RE_VIET_KEEP.sub(r"\1", text)
    return _RE_VIET_REMOVE.sub("", text)


def _to_hiragana(match_text: str, cache: dict) -> tuple[str, str]:
    if match_text in cache:
        return cache[match_text]

    manual = _RE_MANUAL_READING.match(match_text)
    if manual:
        display, hira = manual.groups()
        display = display.strip()
        hira = hira.strip()
    else:
        display = match_text.strip()
        result = _KKS.convert(display)
        hira = "".join([item['hira'] for item in result])

    cache[match_text] = (display, hira)
    return display, hira


# ── Main Processing Logic ──────────────────────────────────────────────────────

def process_furigana(html_string: str) -> tuple[str, str]:
    if not html_string:
        return "", ""

    # 1. Normalize Input: Fully unescape the string first.
    normalized_content = html.unescape(html_string)

    # 2. Separate text bases for the two different tabs
    hover_base = _strip_vietnamese(normalized_content, keep_content=False)
    annotated_base = _strip_vietnamese(normalized_content, keep_content=True)

    # 3. Find all Kanji markers
    matches = _RE_KANJI_MATCH.findall(normalized_content)

    if not matches:
        return hover_base, annotated_base

    # 4. RESTORE LINE SPACING: Convert <p> → <div> with explicit bottom margins
    annotated_html = annotated_base.replace(
        "<p>", "<div style='line-height: 1.6; margin-bottom: 1rem;'>"
    ).replace("</p>", "</div>")

    cache = {}
    hover_html = hover_base

    # 5. Replace markers with appropriate HTML structures
    for match in matches:
        display, hira = _to_hiragana(match, cache)
        marker = f"<<{match}>>"

        # Tooltip format for the "Nội dung" tab (Keeps full tooltip popup active)
        hover_html = hover_html.replace(
            marker,
            f'<span class="add_color_to_kanji html_field_font_size" data-toggle="tooltip" title="{hira}">{display}</span>'
        )

        # Ruby format for the "Chú thích Kanji" tab:
        # - Keeps the span class for text color/styling alongside the static <rt> reading
        annotated_html = annotated_html.replace(
            marker,
            f'<ruby><span class="add_color_to_kanji">{display}</span><rt style="color: #35979c;">{hira}</rt></ruby>'
        )

    # 6. Odoo 19 Sanitizer Defense: Wrap the entire output in a root block tag
    final_annotated = f'<div class="furigana-wrapper">{annotated_html}</div>'

    return hover_html, final_annotated