"""Tests for DecisionService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.database import init_db
from app.services.decision_service import DecisionService


@pytest.fixture
async def decision_service(tmp_path: Path) -> DecisionService:
    """Create a DecisionService with an initialized SQLite database."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    return DecisionService(sqlite_path=db_path, data_dir=str(tmp_path))


async def _create_sample(
    service: DecisionService,
    *,
    game_id: str = "game-1",
    chosen: dict | None = None,
    legal: list[dict] | None = None,
    thinking: str | None = "出最小单张",
) -> str:
    chosen_action = chosen or {"action_type": "SINGLE", "cards": ["C3"]}
    legal_actions = legal or [
        {"action_type": "SINGLE", "cards": ["C3"]},
        {"action_type": "PASS", "cards": []},
    ]
    return await service.create_decision_point(
        game_id=game_id,
        round_number=1,
        player_id="p1",
        hand_cards=[3, 4, 5],
        opponent_hands={"p2": 17},
        last_action=None,
        game_phase="playing",
        legal_actions=legal_actions,
        chosen_action=chosen_action,
        thinking=thinking,
    )


class TestDecisionServiceList:
    """Test decision point listing."""

    @pytest.mark.asyncio
    async def test_list_decision_points_empty(self, decision_service: DecisionService) -> None:
        points, total = await decision_service.list_decision_points()
        assert points == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_decision_points_with_filters(
        self, decision_service: DecisionService
    ) -> None:
        await _create_sample(decision_service)
        points, total = await decision_service.list_decision_points(
            game_id="game-1",
            player_id="p1",
            min_quality=0.0,
            train_usable=True,
        )
        assert total == 1
        assert len(points) == 1
        assert points[0]["train_usable"] is True


class TestDecisionServiceCreate:
    """Test create + train_usable evaluation."""

    @pytest.mark.asyncio
    async def test_illegal_action_not_usable(self, decision_service: DecisionService) -> None:
        dp_id = await _create_sample(
            decision_service,
            chosen={"action_type": "BOMB", "cards": ["C3", "D3", "H3", "S3"]},
            legal=[{"action_type": "PASS", "cards": []}],
            thinking=None,
        )
        item = await decision_service.get_decision_point(dp_id)
        assert item is not None
        assert item["train_usable"] is False

    @pytest.mark.asyncio
    async def test_legal_action_usable(self, decision_service: DecisionService) -> None:
        dp_id = await _create_sample(decision_service, thinking=None)
        item = await decision_service.get_decision_point(dp_id)
        assert item is not None
        assert item["train_usable"] is True


class TestDecisionServiceExport:
    """Test ChatML export options."""

    @pytest.mark.asyncio
    async def test_export_excludes_thinking_by_default(
        self, decision_service: DecisionService, tmp_path: Path
    ) -> None:
        await _create_sample(decision_service, thinking="地主剩3张需管牌")
        path, count = await decision_service.export_chatml(
            include_thinking=False,
            train_usable_only=True,
        )
        assert count == 1
        assert path
        line = Path(path).read_text(encoding="utf-8").strip()
        sample = json.loads(line)
        assistant = sample["messages"][2]["content"]
        assert "原因:" not in assistant
        assert "出" in assistant or "C3" in assistant

    @pytest.mark.asyncio
    async def test_export_includes_thinking_when_enabled(
        self, decision_service: DecisionService
    ) -> None:
        await _create_sample(decision_service, thinking="地主剩3张需管牌")
        path, count = await decision_service.export_chatml(include_thinking=True)
        assert count == 1
        sample = json.loads(Path(path).read_text(encoding="utf-8").strip())
        assert "原因: 地主剩3张需管牌" in sample["messages"][2]["content"]

    @pytest.mark.asyncio
    async def test_export_train_usable_only_filters(
        self, decision_service: DecisionService
    ) -> None:
        await _create_sample(decision_service, thinking=None)
        await _create_sample(
            decision_service,
            game_id="game-2",
            chosen={"action_type": "BOMB", "cards": ["C3"]},
            legal=[{"action_type": "PASS", "cards": []}],
            thinking=None,
        )
        path, count = await decision_service.export_chatml(train_usable_only=True)
        assert count == 1
        assert path

        path_all, count_all = await decision_service.export_chatml(train_usable_only=False)
        assert count_all == 2
        assert path_all


class TestDecisionServiceStats:
    """Test decision point statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, decision_service: DecisionService) -> None:
        stats = await decision_service.get_stats()
        assert stats["total"] == 0
        assert stats["avg_quality"] == 0


class TestDecisionServiceUpdateOutcome:
    """Test updating decision outcomes."""

    @pytest.mark.asyncio
    async def test_update_outcome_nonexistent_game(
        self, decision_service: DecisionService
    ) -> None:
        updated = await decision_service.update_outcome("nonexistent-game", "winner-1")
        assert updated == 0
