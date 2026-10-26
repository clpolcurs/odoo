"""Audio files fetched on the client side: the Odoo server never fetches URLs."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote

import httpx

from .client import USER_AGENT, LJError

AUDIO_MAX_BYTES = 30 * 1024 * 1024
AUDIO_TYPES = {
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".oga": "audio/ogg",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".weba": "audio/webm",
}


@dataclass(frozen=True)
class AudioFile:
    content: bytes
    content_type: str
    filename: str


def audio_type(content_type: str | None, filename: str) -> str | None:
    """The audio/* type to upload a file with, or None if it is not audio.

    An audio/* Content-Type is kept; otherwise a known extension decides, unless the server sent text (an HTML page).
    """
    media = (content_type or "").split(";")[0].strip().lower()
    if media.startswith("audio/"):
        return media
    if media.startswith("text/"):
        return None
    return AUDIO_TYPES.get(PurePosixPath(filename).suffix.lower())


def header_filename(name: str) -> str:
    """X-Filename value: the base name, percent-encoded as UTF-8 (the API decodes it)."""
    base = "".join(char for char in PurePosixPath(name.replace("\\", "/")).name if char.isprintable())
    return quote(base)


async def download_audio(
    url: str,
    *,
    timeout: float,
    max_bytes: int = AUDIO_MAX_BYTES,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AudioFile:
    """GET an http(s) URL, following redirects, and return it if it is audio of at most `max_bytes`."""
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        transport=transport,
        headers={"User-Agent": USER_AGENT},
        event_hooks={"request": [_require_http]},
    ) as client:
        try:
            async with client.stream("GET", url) as response:
                if not response.is_success:
                    raise LJError(f"download of {url} failed: HTTP {response.status_code}")
                filename = _download_filename(response)
                content_type = audio_type(response.headers.get("content-type"), filename)
                if content_type is None:
                    raise LJError(
                        f"{response.url} is not audio (Content-Type {response.headers.get('content-type')!r}); "
                        "give a direct link to the audio file"
                    )
                declared = response.headers.get("content-length", "")
                if declared.isdigit() and int(declared) > max_bytes:
                    raise _too_large(max_bytes)
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise _too_large(max_bytes)
                    chunks.append(chunk)
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            raise LJError(f"download of {url} failed: {type(exc).__name__}: {exc}") from exc
    return AudioFile(b"".join(chunks), content_type, filename)


def read_audio_file(path: str, max_bytes: int = AUDIO_MAX_BYTES) -> AudioFile:
    """Read a local audio file given by its absolute path."""
    file = Path(path).expanduser()
    if not file.is_absolute():
        raise LJError(f"{path!r} is not an absolute path (lj-mcp does not run in your working directory)")
    if not file.is_file():
        raise LJError(f"{file} does not exist or is not a file")
    content_type = audio_type(None, file.name)
    if content_type is None:
        raise LJError(f"{file.name} is not an audio file; known extensions: {', '.join(AUDIO_TYPES)}")
    if file.stat().st_size > max_bytes:
        raise _too_large(max_bytes)
    return AudioFile(file.read_bytes(), content_type, file.name)


async def _require_http(request: httpx.Request) -> None:
    """Checked on every request, so a redirect cannot leave http(s) either."""
    if request.url.scheme not in ("http", "https"):
        raise LJError(f"refusing to download {request.url}: only http and https URLs are allowed")


def _download_filename(response: httpx.Response) -> str:
    disposition = Message()
    disposition["content-disposition"] = response.headers.get("content-disposition", "")
    return disposition.get_filename() or unquote(PurePosixPath(response.url.path).name)


def _too_large(max_bytes: int) -> LJError:
    return LJError(f"the audio file is larger than {max_bytes / 2**20:g} MiB")
