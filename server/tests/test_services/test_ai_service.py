from __future__ import annotations

import pytest

from app.utils.exceptions import (
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitExceededError,
    AITimeoutError,
)
from app.services.ai_service import AIService


class TestAIServiceErrorMapping:
    def test_map_provider_error_to_rate_limit(self) -> None:
        error = AIService._map_provider_error("openai", RuntimeError("429 rate limit exceeded"))

        assert isinstance(error, AIRateLimitExceededError)
        assert error.code == "AI_RATE_LIMIT_EXCEEDED"

    def test_map_provider_error_to_unavailable(self) -> None:
        error = AIService._map_provider_error("openai", RuntimeError("503 service unavailable"))

        assert isinstance(error, AIProviderUnavailableError)
        assert error.code == "AI_PROVIDER_UNAVAILABLE"

    def test_map_provider_error_to_generic_provider_error(self) -> None:
        error = AIService._map_provider_error("openai", RuntimeError("unexpected upstream failure"))

        assert isinstance(error, AIProviderError)
        assert error.code == "AI_PROVIDER_ERROR"

    def test_map_provider_error_preserves_app_error(self) -> None:
        original = AITimeoutError("openai", "timed out")

        error = AIService._map_provider_error("openai", original)

        assert error is original
