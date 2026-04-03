"""Tests for DecisionService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.decision_service import DecisionService


@pytest.fixture
def decision_service(tmp_path: Path) -> DecisionService:
    """Create a DecisionService instance for testing."""
    return DecisionService(
        sqlite_path=str(tmp_path / "test.db"),
        data_dir=str(tmp_path),
    )


class TestDecisionServiceList:
    """Test decision point listing."""

    @pytest.mark.asyncio
    async def test_list_decision_points_empty(self, decision_service: DecisionService) -> None:
        """Test listing decision points when empty."""
        points, total = await decision_service.list_decision_points()
        assert points == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_decision_points_with_filters(self, decision_service: DecisionService) -> None:
        """Test listing decision points with filters."""
        points, total = await decision_service.list_decision_points(
            game_id="game-1",
            player_id="player-1",
            min_quality=0.5,
        )
        assert isinstance(points, list)
        assert isinstance(total, int)


class TestDecisionServiceStats:
    """Test decision point statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, decision_service: DecisionService) -> None:
        """Test getting stats when no decision points exist."""
        stats = await decision_service.get_stats()
        assert stats["total_count"] == 0
        assert stats["avg_quality_score"] is None


class TestDecisionServiceUpdateOutcome:
    """Test updating decision outcomes."""

    @pytest.mark.asyncio
    async def test_update_outcome_nonexistent_game(self, decision_service: DecisionService) -> None:
        """Test updating outcome for non-existent game returns 0."""
        updated = await decision_service.update_outcome("nonexistent-game", "winner-1")
        assert updated == 0
