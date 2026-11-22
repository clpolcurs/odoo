"""Images read from local files, and the paragraph of the markup that an image replaces."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from .client import LJError

IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
WIDTH = re.compile(r"\d+(\.\d+)?(%|px)")


@dataclass(frozen=True)
class ImageFile:
    content: bytes
    content_type: str
    filename: str


def read_image_file(path: str, max_bytes: int = IMAGE_MAX_BYTES) -> ImageFile:
    """Read a local image file given by its absolute path."""
    file = Path(path).expanduser()
    if not file.is_absolute():
        raise LJError(f"{path!r} is not an absolute path (lj-mcp does not run in your working directory)")
    if not file.is_file():
        raise LJError(f"{file} does not exist or is not a file")
    content_type = IMAGE_TYPES.get(file.suffix.lower())
    if content_type is None:
        raise LJError(f"{file.name} is not a PNG, JPEG, WebP or GIF image; known extensions: {', '.join(IMAGE_TYPES)}")
    if file.stat().st_size > max_bytes:
        raise LJError(f"the image is larger than {max_bytes / 2**20:g} MiB")
    return ImageFile(file.read_bytes(), content_type, file.name)


def check_width(width: str | None) -> None:
    if width is not None and not WIDTH.fullmatch(width):
        raise LJError(f"width {width!r} must be a number followed by % or px, e.g. 50% or 320px")


def with_width(tag: str, width: str | None) -> str:
    """The <img> tag with a width as the editor writes it (style="width: 50%;"); NihonGo keeps % and px."""
    check_width(width)
    return tag if width is None else tag.replace("<img ", f'<img style="width: {width};" ', 1)


def placeholder_paragraph(markup: str, placeholder: str) -> re.Match[str]:
    """The one paragraph of the markup that holds only `placeholder`, as text or HTML-escaped."""
    forms = {re.escape(placeholder), re.escape(html.escape(placeholder, quote=False))}
    pattern = re.compile(rf"<p(?:\s[^>]*)?>\s*(?:{'|'.join(forms)})\s*</p>")
    found = list(pattern.finditer(markup))
    if len(found) != 1:
        where = "no paragraph" if not found else f"{len(found)} paragraphs"
        raise LJError(f"{where} of the markup hold only {placeholder!r}; the image must replace exactly one")
    return found[0]
