"""Tests for batch game concurrency limiting."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.events import EventBus
from app.services.game_orchestration_service import GameOrchestrationService


@pytest.mark.asyncio
async def test_game_loops_respect_concurrency_limit() -> None:
    service = GameOrchestrationService(
        engine_registry=MagicMock(),
        collector=MagicMock(),
        ai_service=MagicMock(),
        experiment_config_service=MagicMock(),
        sqlite_path=":memory:",
        event_bus=EventBus(),
        max_concurrent_games=1,
    )

    current = 0
    peak = 0

    async def fake_loop(game_id: str) -> None:
        nonlocal current, peak
        async with service._game_slots:
            current += 1
            peak = max(peak, current)
            await asyncio.sleep(0.05)
            current -= 1

    service._run_game_loop = fake_loop  # type: ignore[method-assign]

    engine = MagicMock()
    engine.initialize.return_value = MagicMock(game_type="doudizhu")
    service._engine_registry.get.return_value = engine

    with patch(
        "app.services.game_orchestration_service.ws_manager"
    ) as mock_ws:
        mock_ws.broadcast = AsyncMock()
        await service.start_game_execution("g1", "doudizhu", ["a", "b", "c"])
        await service.start_game_execution("g2", "doudizhu", ["a", "b", "c"])
        await service.start_game_execution("g3", "doudizhu", ["a", "b", "c"])
        await asyncio.gather(*service._tasks.values())

    assert peak == 1
