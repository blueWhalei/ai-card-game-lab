"""Policy registry.

Symmetric with ``LLMClientFactory`` and ``GameEngineRegistry``. Composite
policies (search, ensemble) will build their members through this registry
instead of hardcoding them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.policy.base import Policy
from app.utils.exceptions import InvalidActionError

PolicyFactory = Callable[[dict[str, Any]], Policy]


class PolicyRegistry:
    """Maps a policy kind to a factory that builds it from config."""

    def __init__(self) -> None:
        self._factories: dict[str, PolicyFactory] = {}

    def register(self, kind: str, factory: PolicyFactory) -> None:
        self._factories[kind] = factory

    def create(self, kind: str, params: dict[str, Any] | None = None) -> Policy:
        """Build a policy.

        Raises:
            InvalidActionError: if no policy of that kind is registered.
        """
        factory = self._factories.get(kind)
        if factory is None:
            raise InvalidActionError(kind, f"No policy registered for kind '{kind}'")
        return factory(params or {})

    def list_kinds(self) -> list[str]:
        return list(self._factories)
