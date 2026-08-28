"""Tests for game loop abort cleanup."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.game_orchestration_service import GameOrchestrationService


@pytest.mark.asyncio
async def test_abort_game_clears_memory_and_updates_status() -> None:
    svc = GameOrchestrationService.__new__(GameOrchestrationService)
    svc._states = {"g1": object()}
    svc._tasks = {"g1": MagicMock()}
    svc._pause_events = {"g1": MagicMock()}

    repo = AsyncMock()
    # Avoid real WS
    import app.services.game_orchestration_service as mod

    original = mod.ws_manager.broadcast
    mod.ws_manager.broadcast = AsyncMock()
    try:
        await svc._abort_game(
            "g1",
            repo,
            status="failed",
            message="boom",
        )
    finally:
        mod.ws_manager.broadcast = original

    repo.update_status.assert_awaited_once_with("g1", "failed")
    assert "g1" not in svc._states
    assert "g1" not in svc._tasks
    assert "g1" not in svc._pause_events
