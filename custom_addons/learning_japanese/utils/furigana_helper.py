import html
import re
import logging
from pykakasi import kakasi

_logger = logging.getLogger(__name__)

# ── Module-level singletons ────────────────────────────────────────────────────
_KKS = kakasi()

# Compiled patterns
_RE_KANJI_MATCH   = re.compile(r"<<([^<>]+)>>")
_RE_VIET_KEEP     = re.compile(r"\{\{(.+?)\}\}",           re.DOTALL)
_RE_VIET_REMOVE   = re.compile(r"(?:<br\s*/?>)?\s*\{\{.+?\}\}", re.DOTALL)
_RE_MANUAL_READING = re.compile(r"^(.+?)\s*-\s*(.+)$")     # e.g. "match - hira"


# ── Vietnamese stripping ───────────────────────────────────────────────────────

def _strip_vietnamese(text: str, keep_content: bool) -> str:
    """
    keep_content=True  → strip {{ }} wrappers, keep inner text  (for content tab)
    keep_content=False → remove <br> + {{ ... }} entirely        (for hover tab)
    """
    if keep_content:
        return _RE_VIET_KEEP.sub(r"\1", text)
    return _RE_VIET_REMOVE.sub("", text)


# ── Kakasi conversion with caching ─────────────────────────────────────────────

def _to_hiragana(match: str, cache: dict) -> tuple[str, str]:
    """
    Convert a kanji match to (display_text, hiragana).
    Handles manual readings via "kanji - reading" syntax.
    Returns cached result if available.
    """
    if match in cache:
        return cache[match]

    manual = _RE_MANUAL_READING.match(match)
    if manual:
        result = manual.group(1).strip(), manual.group(2).strip()
    else:
        hira = "".join(item["hira"] for item in _KKS.convert(match))
        result = match, hira

    cache[match] = result
    return result


# ── Core builder ──────────────────────────────────────────────────────────────

def process_furigana(html_string: str) -> tuple[str, str]:
    """
    Process a raw HTML string and return both furigana variants in one pass.

    Returns:
        (hover_html, annotated_html)
        hover_html     → content_only_kanji: Japanese only, tooltip-style ruby
        annotated_html → content:            Japanese annotated + Vietnamese text
    """
    # Prepare both variants of the HTML string (encoded, Vietnamese handled)
    hover_html      = _strip_vietnamese(html_string, keep_content=False)
    annotated_html  = _strip_vietnamese(html_string, keep_content=True)

    # Find all kanji matches from the decoded text (to handle &lt;&lt; entities)
    decoded         = html.unescape(html_string)
    decoded_clean   = _strip_vietnamese(decoded, keep_content=False)
    matches         = _RE_KANJI_MATCH.findall(decoded_clean)

    if not matches:
        return hover_html, annotated_html

    # Convert <p> → <div> only for the annotated (content) variant
    annotated_html = annotated_html.replace(
        "<p>", "<div style='line-height: 1.5; margin-bottom: 1rem;'>"
    ).replace("</p>", "</div>")

    # Single kakasi pass with caching — shared across both variants
    cache = {}
    for match in matches:
        display, hira = _to_hiragana(match, cache)
        encoded_match = f"&lt;&lt;{match}&gt;&gt;"

        hover_html = hover_html.replace(
            encoded_match,
            f"<span class='add_color_to_kanji' "
            f"data-toggle='tooltip' title='{hira}'>{display}</span>"
        )
        annotated_html = annotated_html.replace(
            encoded_match,
            f"<ruby class='add_color_to_kanji'>{display}"
            f"<rt><span style='font-size: 13px; color: #35979c !important;'>"
            f"<div style='line-height: 2; text-align: center;'>{hira}</div>"
            f"</span></rt></ruby>"
        )

    return hover_html, annotated_html