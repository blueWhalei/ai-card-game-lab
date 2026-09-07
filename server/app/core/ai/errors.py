"""Classifying raw provider failures.

Which HTTP body means "slow down" versus "this provider is down" is a transport
concern, and both the policy layer (deciding whether to retry) and the service
layer (deciding what to report) need the same answer.
"""

from __future__ import annotations

from app.utils.exceptions import (
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitExceededError,
    AppError,
)

RATE_LIMIT_ERROR_MARKERS = (
    "rate limit",
    "too many requests",
    "429",
    "quota exceeded",
)
UNAVAILABLE_ERROR_MARKERS = (
    "service unavailable",
    "temporarily unavailable",
    "bad gateway",
    "gateway error",
    "503",
)


def map_provider_error(provider: str, error: Exception) -> AppError:
    """Turn any exception from a provider call into a typed ``AppError``."""
    if isinstance(error, AppError):
        return error

    detail = str(error).strip() or error.__class__.__name__
    detail_lower = detail.lower()

    if any(marker in detail_lower for marker in RATE_LIMIT_ERROR_MARKERS):
        return AIRateLimitExceededError(provider, detail)
    if any(marker in detail_lower for marker in UNAVAILABLE_ERROR_MARKERS):
        return AIProviderUnavailableError(provider, detail)
    return AIProviderError(provider, detail)
