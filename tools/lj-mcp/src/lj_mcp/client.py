"""Async client of the learning_japanese REST API v1."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import httpx

from . import __version__
from .config import Settings

PAGE_MAX = 200
USER_AGENT = f"lj-mcp/{__version__}"

_HINTS = {
    401: "no valid API key reached Odoo: set LJ_API_KEY to the key of the Odoo user claude-mcp, or in a Claude Code "
    "cloud environment add a network secret for the Odoo host; the key may also be expired or revoked",
    412: "re-read the record, re-apply the change and retry with current_version",
    428: "pass the record's current version",
}


class LJError(Exception):
    """A failure whose message is shown to Claude as the tool error."""


class LJApiError(LJError):
    """An error response of the API: RFC 9457 problem details with a `code`."""

    def __init__(self, status: int, problem: Mapping[str, Any] | None = None, text: str = "") -> None:
        self.status = status
        self.problem = dict(problem or {})
        super().__init__(self._render(text))

    @classmethod
    def from_response(cls, response: httpx.Response) -> LJApiError:
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            return cls(response.status_code, body)
        if location := response.headers.get("location"):
            return cls(response.status_code, text=f"redirected to {location} (check LJ_BASE_URL)")
        text = response.text
        if "html" in response.headers.get("content-type", ""):
            text = re.sub(r"<[^>]*>", " ", text)
        return cls(response.status_code, text=" ".join(text.split())[:300])

    @property
    def code(self) -> str | None:
        return self.problem.get("code")

    @property
    def current_version(self) -> str | None:
        return self.problem.get("current_version")

    def _render(self, text: str) -> str:
        head = f"HTTP {self.status} {self.code}" if self.code else f"HTTP {self.status}"
        detail = self.problem.get("detail") or self.problem.get("title") or text
        lines = [f"{head}: {detail}" if detail else head]
        if self.current_version is not None:
            lines.append(f"current_version: {self.current_version}")
        for error in self.problem.get("errors") or []:
            lines.append("- " + (_field_error(error) if isinstance(error, Mapping) else str(error)))
        if hint := _HINTS.get(self.status):
            lines.append(f"hint: {hint}")
        return "\n".join(lines)


def _field_error(error: Mapping[str, Any]) -> str:
    where = []
    if error.get("index") is not None:
        where.append(f"index {error['index']}")
    if error.get("field"):
        where.append(f"field {error['field']}")
    message = error.get("message") or "invalid"
    return f"{', '.join(where)}: {message}" if where else message


def if_match(version: str) -> str:
    """Quote a record version for the If-Match header (an ETag is accepted as is)."""
    return '"' + version.strip().strip('"') + '"'


class LJClient:
    """Sends requests with the Bearer key and returns the decoded JSON bodies.

    Without LJ_API_KEY no Authorization header is sent: in a Claude Code cloud environment a network secret makes
    the agent proxy add it, so the key never enters the session.
    """

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport
        self._http: httpx.AsyncClient | None = None

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            headers = {"Accept": "application/json, application/problem+json", "User-Agent": USER_AGENT}
            if self.settings.api_key:
                headers["Authorization"] = f"Bearer {self.settings.api_key}"
            self._http = httpx.AsyncClient(
                base_url=self.settings.api_url,
                headers=headers,
                timeout=self.settings.timeout,
                transport=self._transport,
            )
        return self._http

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        version: str | None = None,
    ) -> Any:
        """Send one request; `version` becomes If-Match and None query values are left out."""
        request_headers = dict(headers or {})
        if version is not None:
            request_headers["If-Match"] = if_match(version)
        query = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            response = await self._client().request(
                method, path, params=query, json=json, content=content, headers=request_headers
            )
        except httpx.TimeoutException as exc:
            raise LJError(
                f"{method} {path}: no response from {self.settings.api_url} "
                f"within {self.settings.timeout:g} s (LJ_TIMEOUT)"
            ) from exc
        except httpx.HTTPError as exc:
            reason = f"{type(exc).__name__}: {exc}"
            raise LJError(f"{method} {path}: cannot reach {self.settings.api_url} ({reason})") from exc
        if not response.is_success:
            raise LJApiError.from_response(response)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            content_type = response.headers.get("content-type", "no Content-Type")
            raise LJError(f"{method} {path}: expected JSON, got {content_type}") from None

    async def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def collect(self, path: str, params: Mapping[str, Any], cap: int) -> tuple[list[Any], str | None]:
        """Read a list from its first page, following `next_cursor`, until the last page or `cap` items.

        Returns the items and the cursor to resume from (None once everything was read).
        """
        items: list[Any] = []
        cursor: str | None = None
        while True:
            page = await self.get(path, {**params, "limit": min(PAGE_MAX, cap - len(items)), "cursor": cursor})
            batch = page.get("items") or []
            items.extend(batch)
            cursor = page.get("next_cursor")
            if cursor is None or not batch or len(items) >= cap:
                return items, cursor
