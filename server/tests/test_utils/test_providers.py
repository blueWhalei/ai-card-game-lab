"""Unit tests for provider configuration helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.utils.providers import (
    is_provider_configured,
    looks_like_real_api_key,
    probe_ollama_ready,
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
    class _Resp:
        def read(self) -> bytes:
            return b'{"models":[{"name":"qwen2.5:7b"}]}'

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=_Resp()):
        assert probe_ollama_ready("http://localhost:11434") is True

    class _Empty:
        def read(self) -> bytes:
            return b'{"models":[]}'

        def __enter__(self) -> _Empty:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=_Empty()):
        assert probe_ollama_ready("http://localhost:11434") is False


def test_probe_ollama_ready_unreachable() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("down")):
        assert probe_ollama_ready("http://localhost:11434") is False


def test_unknown_provider_unconfigured() -> None:
    assert is_provider_configured(MagicMock(), "not-a-vendor") is False
