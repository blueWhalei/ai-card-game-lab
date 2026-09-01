"""LLM provider configuration helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings

PROVIDER_KEY_ATTRS: dict[str, str] = {
    "openai": "openai_api_key",
    "deepseek": "deepseek_api_key",
    "kimi": "kimi_api_key",
    "dashscope": "dashscope_api_key",
    "zhipu": "zhipu_api_key",
    "minimax": "minimax_api_key",
    "yi": "yi_api_key",
    "baichuan": "baichuan_api_key",
}

# Values that must not count as a real key (common .env.example / local test leftovers).
_PLACEHOLDER_API_KEYS = frozenset(
    {
        "",
        "your-key-here",
        "changeme",
        "change-me",
        "test",
        "xxx",
        "sk-xxx",
        "sk-your-key-here",
        "sk-your-deepseek-key",
        "sk-your-openai-key",
        "none",
        "null",
        "placeholder",
    }
)


def looks_like_real_api_key(value: str | None) -> bool:
    """Return True if *value* looks like a configured secret, not a placeholder."""
    if value is None:
        return False
    key = value.strip()
    if not key:
        return False
    return key.lower() not in _PLACEHOLDER_API_KEYS


def probe_ollama_ready(base_url: str, *, timeout_s: float = 0.8) -> bool:
    """Return True when Ollama responds and reports at least one local model.

    Installing the Ollama app alone is not enough — users must pull/create a model.
    """
    root = base_url.rstrip("/")
    url = f"{root}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        models = payload.get("models")
        return isinstance(models, list) and len(models) > 0
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return False


def is_provider_configured(settings: Settings, provider: str) -> bool:
    """Return whether *provider* can be used with the current settings.

    Cloud providers need a non-placeholder API key (OS env overrides ``.env``).
    Ollama is ready only when the daemon is reachable and has ≥1 local model.
    Unknown providers are treated as unconfigured.
    """
    if provider == "ollama":
        return probe_ollama_ready(settings.ollama_base_url)
    attr = PROVIDER_KEY_ATTRS.get(provider)
    if attr is None:
        return False
    return looks_like_real_api_key(getattr(settings, attr, ""))


def unconfigured_providers_from_players(
    settings: Settings,
    players: list[dict[str, Any]],
) -> list[str]:
    """Return sorted unique provider ids from protocol/live players that are not ready."""
    missing: set[str] = set()
    for player in players:
        model_cfg = player.get("model_config") or {}
        if not isinstance(model_cfg, dict):
            continue
        provider = str(model_cfg.get("provider") or "").strip()
        if provider and not is_provider_configured(settings, provider):
            missing.add(provider)
    return sorted(missing)
