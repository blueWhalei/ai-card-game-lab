"""Unit tests for provider configuration helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.config import Settings
from app.utils.providers import (
    is_provider_configured,
    looks_like_real_api_key,
    probe_ollama_ready,
    unconfigured_providers_from_players,
)


def test_looks_like_real_api_key_rejects_placeholders() -> None:
    assert looks_like_real_api_key("") is False
    assert looks_like_real_api_key("   ") is False
    assert looks_like_real_api_key("your-key-here") is False
    assert looks_like_real_api_key("test") is False
    assert looks_like_real_api_key("TEST") is False
    assert looks_like_real_api_key("sk-abc123real") is True


def test_cloud_provider_uses_key_not_placeholder() -> None:
    settings = Settings(deepseek_api_key="test", minimax_api_key="")
    assert is_provider_configured(settings, "deepseek") is False
    assert is_provider_configured(settings, "minimax") is False

    settings = Settings(deepseek_api_key="sk-real-key-value")
    assert is_provider_configured(settings, "deepseek") is True


def test_ollama_requires_reachable_daemon_with_models() -> None:
    settings = Settings(ollama_base_url="http://localhost:11434")
    with patch("app.utils.providers.probe_ollama_ready", return_value=False):
        assert is_provider_configured(settings, "ollama") is False
    with patch("app.utils.providers.probe_ollama_ready", return_value=True):
        assert is_provider_configured(settings, "ollama") is True


def test_probe_ollama_ready_parses_tags() -> None:
    with patch("app.utils.providers.fetch_model_catalog", return_value={"qwen2.5:7b"}):
        assert probe_ollama_ready("http://localhost:11434")
    with patch("app.utils.providers.fetch_model_catalog", return_value=set()):
        assert not probe_ollama_ready("http://localhost:11434")


def test_probe_ollama_ready_unreachable() -> None:
    with patch("app.utils.providers.fetch_model_catalog", side_effect=httpx.ConnectError("down")):
        assert not probe_ollama_ready("http://localhost:11434")


def test_unknown_provider_unconfigured() -> None:
    assert is_provider_configured(MagicMock(), "not-a-vendor") is False


def test_unconfigured_providers_skip_baseline_seats() -> None:
    settings = Settings(openai_api_key="sk-real-key-value")
    # Force openai unconfigured regardless of .env / constructor merge.
    with patch("app.utils.providers.is_provider_configured", return_value=False):
        missing = unconfigured_providers_from_players(
            settings,
            [
                {"policy_kind": "heuristic", "model_config": {"provider": "openai"}},
                {"policy_kind": "llm", "model_config": {"provider": "openai"}},
            ],
        )
    assert missing == ["openai"]

    with patch("app.utils.providers.is_provider_configured", return_value=False):
        only_baseline = unconfigured_providers_from_players(
            settings,
            [{"policy_kind": "random", "model_config": {"provider": "openai"}}],
        )
    assert only_baseline == []
