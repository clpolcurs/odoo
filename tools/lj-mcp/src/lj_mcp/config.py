"""Settings read from the environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://oht-t4-hcet.com"
DEFAULT_TIMEOUT = 30.0
API_PREFIX = "/api/lj/v1"


class ConfigError(Exception):
    """The environment does not configure lj-mcp correctly."""


@dataclass(frozen=True)
class Settings:
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = field(default=None, repr=False)
    allow_delete: bool = False
    timeout: float = DEFAULT_TIMEOUT

    @property
    def api_url(self) -> str:
        return self.base_url + API_PREFIX

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Read LJ_BASE_URL, LJ_API_KEY, LJ_ALLOW_DELETE and LJ_TIMEOUT."""
        env = os.environ if env is None else env
        api_key = env.get("LJ_API_KEY", "").strip()
        if api_key.startswith("${"):  # placeholder of .mcp.json left unexpanded
            api_key = ""
        return cls(
            base_url=(env.get("LJ_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/"),
            api_key=api_key or None,
            allow_delete=env.get("LJ_ALLOW_DELETE", "").strip().lower() in {"1", "true"},
            timeout=_parse_timeout(env.get("LJ_TIMEOUT", "")),
        )

    def require_api_key(self) -> str:
        if not self.api_key:
            raise ConfigError(
                "LJ_API_KEY is not set. Create an API key for the Odoo user claude-mcp "
                "(Preferences > Account Security > New API Key), export LJ_API_KEY and restart Claude Code."
            )
        return self.api_key


def _parse_timeout(raw: str) -> float:
    if not raw.strip():
        return DEFAULT_TIMEOUT
    try:
        timeout = float(raw)
    except ValueError:
        raise ConfigError(f"LJ_TIMEOUT must be a number of seconds, got {raw!r}") from None
    if timeout <= 0:
        raise ConfigError(f"LJ_TIMEOUT must be positive, got {raw!r}")
    return timeout
