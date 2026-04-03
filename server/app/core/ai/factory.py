"""Factory for creating LLM client instances by provider name."""

from typing import Any

from app.core.ai.base import LLMClient
from app.utils.exceptions import AIProviderError


class LLMClientFactory:
    """Registry-based factory that maps provider names to client classes."""

    def __init__(self) -> None:
        self._client_classes: list[type[LLMClient]] = []

    def register(self, client_class: type[LLMClient]) -> None:
        """Register a concrete LLM client class."""
        self._client_classes.append(client_class)

    def create(self, provider: str, **kwargs: Any) -> LLMClient:
        """Instantiate a client for the requested provider.

        Raises:
            AIProviderError: If no registered client supports *provider*.
        """
        for cls in self._client_classes:
            instance = cls(**kwargs)
            if instance.supports(provider):
                return instance
        raise AIProviderError(provider, "No registered client supports this provider")
