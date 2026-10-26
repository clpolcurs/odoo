import json

import httpx
import pytest
from helpers import API, SETTINGS, FakeApi, problem

from lj_mcp.client import LJApiError, LJClient, LJError
from lj_mcp.config import Settings

pytestmark = pytest.mark.anyio

ODOO_401 = """<!doctype html>
<html lang=en>
<title>401 Unauthorized</title>
<h1>Unauthorized</h1>
<p>User not authenticated, use an API Key with a Bearer Authorization header.</p>
"""


def client(fake: FakeApi, settings: Settings = SETTINGS) -> LJClient:
    return LJClient(settings, transport=fake.transport)


async def test_sends_the_bearer_key(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/books/3", {"id": 3})
    assert await client(fake).get("/books/3") == {"id": 3}
    (request,) = fake.requests
    assert request.headers["Authorization"] == "Bearer secret-key"
    assert "application/json" in request.headers["Accept"]
    assert "If-Match" not in request.headers


async def test_query_leaves_out_none(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/comprehensives", {"items": [], "next_cursor": None})
    await client(fake).get("/comprehensives", {"q": None, "level": "N2", "published": True, "limit": 50})
    assert dict(fake.requests[0].url.params) == {"level": "N2", "published": "true", "limit": "50"}


@pytest.mark.parametrize("version", ["3f9a", '"3f9a"', ' "3f9a" '])
async def test_sends_the_version_as_quoted_if_match(fake: FakeApi, version: str) -> None:
    fake.on("PATCH", f"{API}/comprehensives/58", {"id": 58, "version": "4b2c"})
    await client(fake).request("PATCH", "/comprehensives/58", json={"title": "x"}, version=version)
    (request,) = fake.requests
    assert request.headers["If-Match"] == '"3f9a"'
    assert json.loads(request.content) == {"title": "x"}


async def test_without_a_key_sends_no_authorization(fake: FakeApi) -> None:
    """A network secret of a Claude Code cloud environment then makes the agent proxy add it."""
    fake.on("GET", f"{API}/books", {"items": [], "next_cursor": None})
    await client(fake, Settings(base_url="https://lj.test")).get("/books")
    assert "Authorization" not in fake.requests[0].headers


async def test_412_gives_the_current_version(fake: FakeApi) -> None:
    fake.on(
        "PATCH",
        f"{API}/comprehensives/58",
        lambda request: problem(
            412, "version-mismatch", "The record changed since that version.", current_version="9c1d"
        ),
    )
    with pytest.raises(LJApiError) as caught:
        await client(fake).request("PATCH", "/comprehensives/58", json={"title": "x"}, version="3f9a")
    error = caught.value
    assert (error.status, error.code, error.current_version) == (412, "version-mismatch", "9c1d")
    assert str(error).splitlines() == [
        "HTTP 412 version-mismatch: The record changed since that version.",
        "current_version: 9c1d",
        "hint: re-read the record, re-apply the change and retry with current_version",
    ]


async def test_422_lists_the_field_errors(fake: FakeApi) -> None:
    errors = [
        {"index": 3, "field": "term", "message": "must not be empty"},
        {"field": "level", "message": "not a level"},
    ]
    fake.on(
        "POST",
        f"{API}/vocabularies",
        lambda request: problem(422, "validation-error", "2 invalid fields", errors=errors),
    )
    with pytest.raises(LJApiError) as caught:
        await client(fake).request("POST", "/vocabularies", json={"term": ""})
    assert str(caught.value).splitlines() == [
        "HTTP 422 validation-error: 2 invalid fields",
        "- index 3, field term: must not be empty",
        "- field level: not a level",
    ]


async def test_errors_without_a_problem_body(fake: FakeApi) -> None:
    fake.on("GET", f"{API}/books", lambda request: httpx.Response(401, html=ODOO_401))
    fake.on("GET", f"{API}/tags", lambda request: httpx.Response(502, text="<html>\n  Bad   Gateway</html>"))
    fake.on(
        "GET", f"{API}/meta", lambda request: httpx.Response(303, headers={"Location": "https://lj.test/web/login"})
    )
    messages = []
    for path in ("/books", "/tags", "/meta"):
        with pytest.raises(LJApiError) as caught:
            await client(fake).get(path)
        messages.append(str(caught.value))
    assert messages == [
        "HTTP 401: 401 Unauthorized Unauthorized User not authenticated, use an API Key with a Bearer Authorization "
        "header.\nhint: no valid API key reached Odoo: set LJ_API_KEY to the key of the Odoo user claude-mcp, or in a "
        "Claude Code cloud environment add a network secret for the Odoo host; the key may also be expired or revoked",
        "HTTP 502: <html> Bad Gateway</html>",
        "HTTP 303: redirected to https://lj.test/web/login (check LJ_BASE_URL)",
    ]


async def test_network_failures_are_reported(fake: FakeApi) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    fake.on("GET", f"{API}/books", refuse)
    with pytest.raises(LJError, match=r"cannot reach https://lj.test/api/lj/v1 \(ConnectError: connection refused\)"):
        await client(fake).get("/books")


async def test_collect_follows_next_cursor(fake: FakeApi) -> None:
    pages = {None: ([1, 2], "c2"), "c2": ([3], "c3"), "c3": ([4], None)}

    def page(request: httpx.Request) -> httpx.Response:
        ids, next_cursor = pages[request.url.params.get("cursor")]
        return httpx.Response(200, json={"items": [{"id": id_} for id_ in ids], "next_cursor": next_cursor})

    fake.on("GET", f"{API}/comprehensives", page)
    items, cursor = await client(fake).collect("/comprehensives", {"book_id": 3}, cap=500)
    assert [item["id"] for item in items] == [1, 2, 3, 4]
    assert cursor is None
    assert [request.url.params.get("cursor") for request in fake.requests] == [None, "c2", "c3"]
    assert {request.url.params["book_id"] for request in fake.requests} == {"3"}


async def test_collect_stops_at_the_cap(fake: FakeApi) -> None:
    def page(request: httpx.Request) -> httpx.Response:
        start, limit = int(request.url.params.get("cursor", 0)), int(request.url.params["limit"])
        items = [{"id": id_} for id_ in range(start, start + limit)]
        return httpx.Response(200, json={"items": items, "next_cursor": str(start + limit)})

    fake.on("GET", f"{API}/comprehensives", page)
    items, cursor = await client(fake).collect("/comprehensives", {}, cap=450)
    assert len(items) == 450
    assert cursor == "450"
    assert [request.url.params["limit"] for request in fake.requests] == ["200", "200", "50"]
