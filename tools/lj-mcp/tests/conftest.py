import pytest
from helpers import FakeApi


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fake() -> FakeApi:
    return FakeApi()
