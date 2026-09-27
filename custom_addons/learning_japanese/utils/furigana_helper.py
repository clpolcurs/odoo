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

# Matches <pre>...</pre> and <code>...</code> blocks (pasted source code),
# so their raw content can be shielded from furigana/Vietnamese processing.
_RE_CODE_BLOCK = re.compile(r"<(pre|code)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)

# Placeholder markers used while code blocks are shielded, delimited with NUL
# bytes. NUL cannot appear in real HTML text and is left untouched by
# html.unescape(), so it is safe as a collision-proof marker.
_CODE_PLACEHOLDER_FMT = "\x00CODEBLOCK{}\x00"
_RE_CODE_PLACEHOLDER = re.compile(r"\x00CODEBLOCK(\d+)\x00")


# ── Helper Functions ───────────────────────────────────────────────────────────

def _shield_code_blocks(text: str) -> tuple[str, list[str]]:
    """
    Replace every <pre>/<code> block with a placeholder so later steps
    (unescape, Vietnamese stripping, kanji-marker replacement) never touch
    code content such as `<int>`, `{{...}}` initializer lists, etc.
    """
    blocks: list[str] = []

    def _store(m: re.Match) -> str:
        blocks.append(m.group(0))
        return _CODE_PLACEHOLDER_FMT.format(len(blocks) - 1)

    shielded = _RE_CODE_BLOCK.sub(_store, text)
    return shielded, blocks


def _unshield_code_blocks(text: str, blocks: list[str]) -> str:
    if not blocks:
        return text
    return _RE_CODE_PLACEHOLDER.sub(lambda m: blocks[int(m.group(1))], text)


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

    # 0. Shield <pre>/<code> blocks first: raw pasted code must survive
    #    untouched (no unescape, no {{...}} stripping, no <<...>> conversion).
    shielded_content, code_blocks = _shield_code_blocks(html_string)

    # 1. Normalize Input: Fully unescape the string first.
    normalized_content = html.unescape(shielded_content)

    # 2. Separate text bases for the two different tabs
    hover_base = _strip_vietnamese(normalized_content, keep_content=False)
    annotated_base = _strip_vietnamese(normalized_content, keep_content=True)

    # 3. Find all Kanji markers
    matches = _RE_KANJI_MATCH.findall(normalized_content)

    if not matches:
        return (
            _unshield_code_blocks(hover_base, code_blocks),
            _unshield_code_blocks(annotated_base, code_blocks),
        )

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
            f'<ruby><span class="add_color_to_kanji">{display}</span><rt style="margin-top: 0.5rem; color: #35979c; position: relative; top: -4px; font-size: 0.6em;">{hira}</rt></ruby>'
        )

    # 6. Odoo 19 Sanitizer Defense: Wrap the entire output in a root block tag
    final_annotated = f'<div>{annotated_html}</div>'

    # 7. Restore shielded code blocks to their original, untouched markup.
    hover_html = _unshield_code_blocks(hover_html, code_blocks)
    final_annotated = _unshield_code_blocks(final_annotated, code_blocks)

    return hover_html, final_annotated
