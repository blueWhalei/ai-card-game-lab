"""LLM provider configuration helpers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx

from app.core.policy.kinds import is_baseline_policy_kind, normalize_player_policy_kind

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


def fetch_model_catalog(
    base_url: str, *, ollama: bool, api_key: str = "", timeout_s: float = 4.0
) -> set[str]:
    """Read model metadata without sending prompts or forwarding credentials on redirects."""
    path, collection, field = ("api/tags", "models", "name") if ollama else ("models", "data", "id")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = httpx.get(f"{base_url.rstrip('/')}/{path}", headers=headers, timeout=timeout_s)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get(collection) if isinstance(payload, dict) else None
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get(field), str) for row in rows
    ):
        raise ValueError("Invalid model catalog")
    return {row[field] for row in rows}


def model_in_catalog(model: str, names: set[str], *, ollama: bool) -> bool:
    if ollama and ":" not in model.rsplit("/", 1)[-1]:
        return model in names or f"{model}:latest" in names
    return model in names


def probe_ollama_ready(base_url: str, *, timeout_s: float = 0.8) -> bool:
    try:
        names = fetch_model_catalog(base_url, ollama=True, timeout_s=timeout_s)
    except (httpx.HTTPError, ValueError, httpx.InvalidURL):
        return False
    return bool(names)


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


def _seat_config_checks(settings: Settings, players: list[dict[str, Any]]) -> list[dict[str, str]]:
    checks = []
    for player in players:
        if is_baseline_policy_kind(normalize_player_policy_kind(player.get("policy_kind"))):
            continue
        cfg = player.get("model_config") or {}
        provider = str(cfg.get("provider") or "")
        model = str(cfg.get("model_name") or "")
        status, setting = "configured", ""
        if provider != "ollama" and provider not in PROVIDER_KEY_ATTRS:
            status = "unknown_provider"
        elif not model.strip() or model != model.strip():
            status = "invalid_model"
        elif not _valid_base_url(getattr(settings, f"{provider}_base_url")):
            status, setting = "invalid_url", f"{provider.upper()}_BASE_URL"
        elif provider != "ollama" and not is_provider_configured(settings, provider):
            status, setting = "missing_key", PROVIDER_KEY_ATTRS[provider].upper()
        checks.append(
            {
                "player_id": str(player.get("id") or ""),
                "provider": provider,
                "model": model,
                "status": status,
                "setting": setting,
            }
        )
    return checks


def _valid_base_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        return bool(url.scheme in {"http", "https"} and url.hostname)
    except ValueError:
        return False


def _probe_catalog(settings: Settings, provider: str) -> tuple[str, set[str]]:
    ollama = provider == "ollama"
    try:
        names = fetch_model_catalog(
            getattr(settings, f"{provider}_base_url"),
            ollama=ollama,
            api_key="" if ollama else getattr(settings, PROVIDER_KEY_ATTRS[provider]),
        )
        return "listed", names
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            return "access_denied", set()
        return "catalog_unavailable", set()
    except (httpx.RequestError, httpx.InvalidURL):
        return "unreachable", set()
    except ValueError:
        return "catalog_unavailable", set()


async def seat_model_checks(
    settings: Settings, players: list[dict[str, Any]], *, check_connection: bool
) -> list[dict[str, str]]:
    checks = _seat_config_checks(settings, players)
    if check_connection:
        providers = sorted({c["provider"] for c in checks if c["status"] == "configured"})
        results = await asyncio.gather(
            *(asyncio.to_thread(_probe_catalog, settings, provider) for provider in providers)
        )
        catalogs = dict(zip(providers, results, strict=True))
        for check in checks:
            if check["status"] != "configured":
                continue
            provider = check["provider"]
            status, names = catalogs[provider]
            if status == "listed" and not model_in_catalog(
                check["model"], names, ollama=provider == "ollama"
            ):
                status = "not_listed"
            check["status"] = status
    return checks


def unconfigured_providers_from_players(
    settings: Settings,
    players: list[dict[str, Any]],
) -> list[str]:
    """Return sorted unique provider ids from protocol/live players that are not ready."""
    missing: set[str] = set()
    ollama_models: set[str] = set()
    for check in _seat_config_checks(settings, players):
        provider = check["provider"]
        if check["status"] != "configured":
            missing.add(provider or "(missing provider)")
        elif provider == "ollama":
            ollama_models.add(check["model"])
    if ollama_models:
        status, names = _probe_catalog(settings, "ollama")
        if status != "listed" or any(
            not model_in_catalog(model, names, ollama=True) for model in ollama_models
        ):
            missing.add("ollama")
    return sorted(missing)
