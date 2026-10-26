"""Test helpers: a fake API behind httpx.MockTransport and an in-memory MCP client session."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from lj_mcp.config import Settings
from lj_mcp.server import build_server

API = "https://lj.test/api/lj/v1"
SETTINGS = Settings(base_url="https://lj.test", api_key="secret-key", timeout=5)

Handler = Callable[[httpx.Request], httpx.Response]


def problem(status: int, code: str, detail: str, **members: Any) -> httpx.Response:
    """An application/problem+json response as the API sends it."""
    body = {"type": f"urn:lj:problem:{code}", "title": detail, "status": status, "code": code, "detail": detail}
    return httpx.Response(status, json=body | members, headers={"Content-Type": "application/problem+json"})


class FakeApi:
    """Answers each request by method and URL (without the query) and records the requests."""

    def __init__(self) -> None:
        self.handlers: dict[tuple[str, str], Handler] = {}
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def on(self, method: str, url: str, answer: Handler | Any) -> None:
        """Answer with `answer(request)` when it is callable, else with `answer` as the JSON body."""
        self.handlers[method, url] = answer if callable(answer) else lambda request: httpx.Response(200, json=answer)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        handler = self.handlers.get((request.method, str(request.url).split("?")[0]))
        if handler is None:
            raise AssertionError(f"unexpected request: {request.method} {request.url}")
        return handler(request)


@asynccontextmanager
async def mcp_session(fake: FakeApi, settings: Settings = SETTINGS) -> AsyncIterator[ClientSession]:
    server = build_server(settings, transport=fake.transport)
    async with create_connected_server_and_client_session(server) as session:
        yield session


async def call(session: ClientSession, tool: str, **arguments: Any) -> Any:
    """Call a tool and decode its JSON result; a tool error fails the test."""
    result = await session.call_tool(tool, arguments)
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


async def call_error(session: ClientSession, tool: str, **arguments: Any) -> str:
    """Call a tool that must fail and return its error message."""
    result = await session.call_tool(tool, arguments)
    assert result.isError
    return result.content[0].text
