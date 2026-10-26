from pathlib import Path
from typing import Any

import httpx
import pytest

from lj_mcp.audio import AUDIO_MAX_BYTES, AudioFile, download_audio, header_filename, read_audio_file
from lj_mcp.client import LJError

MIB = 1024 * 1024


def serve(**response: Any) -> httpx.MockTransport:
    """A transport answering every request with 200 and these httpx.Response arguments."""
    return httpx.MockTransport(lambda request: httpx.Response(200, **response))


@pytest.mark.anyio
async def test_aborts_a_download_over_the_size_limit() -> None:
    chunk, sent = bytes(MIB), []

    async def body():
        for _ in range(64):
            sent.append(chunk)
            yield chunk

    transport = serve(headers={"Content-Type": "audio/mpeg"}, content=body())
    with pytest.raises(LJError, match="larger than 30 MiB"):
        await download_audio("https://files.test/big.mp3", timeout=5, transport=transport)
    assert len(sent) <= 32  # stopped right after the limit, not at the end of the 64 MiB


@pytest.mark.anyio
async def test_rejects_a_declared_size_over_the_limit_without_reading() -> None:
    sent = []

    async def body():
        sent.append(1)
        yield b"ID3"

    headers = {"Content-Type": "audio/mpeg", "Content-Length": str(AUDIO_MAX_BYTES + 1)}
    with pytest.raises(LJError, match="larger than 30 MiB"):
        await download_audio("https://files.test/a.mp3", timeout=5, transport=serve(headers=headers, content=body()))
    assert sent == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("url", "content_type"),
    [
        ("https://drive.test/file/d/1/view.mp3", "text/html; charset=utf-8"),
        ("https://files.test/data", "application/json"),
        ("https://files.test/notes", None),
    ],
)
async def test_rejects_content_that_is_not_audio(url: str, content_type: str | None) -> None:
    headers = {"Content-Type": content_type} if content_type else {}
    with pytest.raises(LJError, match="is not audio"):
        await download_audio(url, timeout=5, transport=serve(headers=headers, content=b"<html></html>"))


@pytest.mark.anyio
async def test_accepts_an_audio_extension_with_a_generic_content_type() -> None:
    transport = serve(headers={"Content-Type": "application/octet-stream"}, content=b"ID3 data")
    audio = await download_audio("https://files.test/a/n2-dd-1ban.mp3?sig=1", timeout=5, transport=transport)
    assert audio == AudioFile(b"ID3 data", "audio/mpeg", "n2-dd-1ban.mp3")


@pytest.mark.anyio
async def test_follows_redirects_and_takes_the_attachment_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "share.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/blob/7"})
        disposition = "attachment; filename*=UTF-8''%E8%81%B4%E8%A7%A3.m4a"
        return httpx.Response(
            200, headers={"Content-Type": "audio/mp4", "Content-Disposition": disposition}, content=b"m4a"
        )

    audio = await download_audio("https://share.test/s/abc", timeout=5, transport=httpx.MockTransport(handler))
    assert audio == AudioFile(b"m4a", "audio/mp4", "聴解.m4a")


@pytest.mark.anyio
@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://files.test/a.mp3", "files.test/a.mp3"])
async def test_only_downloads_http_urls(url: str) -> None:
    with pytest.raises(LJError, match="only http and https"):
        await download_audio(url, timeout=5, transport=serve(content=b""))


@pytest.mark.anyio
async def test_does_not_follow_a_redirect_out_of_http() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(302, headers={"Location": "file:///etc/passwd"}))
    with pytest.raises(LJError, match="only http and https"):
        await download_audio("https://files.test/a.mp3", timeout=5, transport=transport)


@pytest.mark.anyio
async def test_reports_http_errors_of_the_download() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    with pytest.raises(LJError, match="HTTP 404"):
        await download_audio("https://files.test/a.mp3", timeout=5, transport=transport)


def test_reads_a_local_audio_file(tmp_path: Path) -> None:
    file = tmp_path / "n2-dd-1ban.mp3"
    file.write_bytes(b"ID3 data")
    assert read_audio_file(str(file)) == AudioFile(b"ID3 data", "audio/mpeg", "n2-dd-1ban.mp3")


def test_refuses_local_files_that_are_not_usable(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    big = tmp_path / "big.wav"
    with big.open("wb") as handle:
        handle.truncate(AUDIO_MAX_BYTES + 1)  # sparse file
    with pytest.raises(LJError, match="not an absolute path"):
        read_audio_file("audio/a.mp3")
    with pytest.raises(LJError, match="does not exist"):
        read_audio_file(str(tmp_path / "missing.mp3"))
    with pytest.raises(LJError, match="not an audio file"):
        read_audio_file(str(notes))
    with pytest.raises(LJError, match="larger than 30 MiB"):
        read_audio_file(str(big))


def test_header_filename() -> None:
    assert header_filename("n2-dd-1ban.mp3") == "n2-dd-1ban.mp3"
    assert header_filename("../../etc/x.mp3") == "x.mp3"
    assert header_filename("C:\\audio\\聴解.mp3") == "%E8%81%B4%E8%A7%A3.mp3"
    assert header_filename("1 ban 100%.mp3") == "1%20ban%20100%25.mp3"
