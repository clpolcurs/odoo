import pytest

from lj_mcp.config import ConfigError, Settings


def test_defaults() -> None:
    settings = Settings.from_env({})
    assert settings.api_url == "https://oht-t4-hcet.com/api/lj/v1"
    assert settings.api_key is None
    assert settings.allow_delete is False
    assert settings.timeout == 30


def test_reads_the_environment() -> None:
    env = {"LJ_BASE_URL": "https://lj.test/", "LJ_API_KEY": " key ", "LJ_ALLOW_DELETE": "TRUE", "LJ_TIMEOUT": "2.5"}
    assert Settings.from_env(env) == Settings(base_url="https://lj.test", api_key="key", allow_delete=True, timeout=2.5)


@pytest.mark.parametrize(("raw", "expected"), [("1", True), ("true", True), ("0", False), ("yes", False), ("", False)])
def test_allow_delete(raw: str, expected: bool) -> None:
    assert Settings.from_env({"LJ_ALLOW_DELETE": raw}).allow_delete is expected


@pytest.mark.parametrize("raw", ["30s", "0", "-1"])
def test_rejects_a_bad_timeout(raw: str) -> None:
    with pytest.raises(ConfigError, match="LJ_TIMEOUT"):
        Settings.from_env({"LJ_TIMEOUT": raw})


@pytest.mark.parametrize("raw", ["", "  ", "${LJ_API_KEY}", "${LJ_API_KEY:-}"])
def test_missing_api_key(raw: str) -> None:
    assert Settings.from_env({"LJ_API_KEY": raw}).api_key is None


def test_repr_hides_the_api_key() -> None:
    assert "s3cret" not in repr(Settings(api_key="s3cret"))
