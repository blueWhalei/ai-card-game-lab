"""LLM provider configuration helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def is_provider_configured(settings: Settings, provider: str) -> bool:
    """Return whether *provider* can be used with the current settings.

    Ollama needs no API key. Unknown providers are treated as unconfigured.
    """
    if provider == "ollama":
        return True
    attr = PROVIDER_KEY_ATTRS.get(provider)
    if attr is None:
        return False
    return bool(getattr(settings, attr, ""))
