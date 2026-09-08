"""Service tests for DPO preference export."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.ai.prompt import PromptBuilder
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.eval.rollout import EvaluatorParams
from app.database import init_db
from app.services.ai_service import AIService
from app.services.decision_eval import DecisionEvaluator
from app.services.decision_service import DecisionService

_FAST = EvaluatorParams(determinizations=1, rollouts_per_world=1, max_candidates=3)
_PROMPT = [{"role": "user", "content": "pick"}]


@pytest.fixture
async def decision_service(tmp_path: Path) -> DecisionService:
    db_path = str(tmp_path / "pref.db")
    await init_db(db_path)
    return DecisionService(sqlite_path=db_path, data_dir=str(tmp_path))


async def _create_pref_ready(
    service: DecisionService,
    *,
    action_id: str = "PASS||",
    best_action_id: str = "PLAY|3|",
    ev_loss: float = 0.2,
    round_number: int = 1,
) -> str:
    return await service.create_decision_point(
        game_id="game-1",
        round_number=round_number,
        player_id="p1",
        hand_cards=[3, 4, 5],
        opponent_hands={"p2": 17},
        last_action=None,
        game_phase="playing",
        legal_actions=[
            {"id": "PLAY|3|", "action_type": "PLAY", "cards": ["3"]},
            {"id": "PASS||", "action_type": "PASS", "cards": []},
        ],
        chosen_action={"action_type": "PASS", "cards": []},
        action_id=action_id,
        prompt_messages=_PROMPT,
        thinking="pass",
        ev_loss=ev_loss,
        evaluator_params={
            "determinizations": 4,
            "best_action_id": best_action_id,
            "action_values": {action_id: 0.1, best_action_id: 0.9},
        },
    )


class TestScorePathPersistsBest:
    async def test_score_decision_merges_best_into_params(self) -> None:
        engine = DoudizhuEngine()
        state = engine.initialize(["p1", "p2", "p3"], deal_seed=7)
        player_id = engine.get_current_player(state)
        legal = engine.legal_actions(state, player_id)
        action = engine.resolve_action(state, player_id, legal[0].id)

        service = AIService(
            llm_factory=MagicMock(),
            prompt_builder=PromptBuilder(),
            decision_evaluator=DecisionEvaluator(_FAST),
        )
        loss, params = await service._score_decision(engine, state, player_id, action)

        assert loss is not None
        assert params is not None
        assert isinstance(params["best_action_id"], str)
        assert params["best_action_id"]
        assert isinstance(params["action_values"], dict)
        assert params["best_action_id"] in params["action_values"]
        assert "determinizations" in params
        assert isinstance(params["candidates_evaluated"], int)
        assert params["candidates_evaluated"] > 0
        assert isinstance(params["legal_action_count"], int)
        assert params["legal_action_count"] >= params["candidates_evaluated"]
        assert isinstance(params["truncated"], bool)


class TestExportPreferences:
    async def test_export_yields_pair(self, decision_service: DecisionService) -> None:
        await _create_pref_ready(decision_service)

        filepath, count, meta = await decision_service.export_preferences(
            train_usable_only=False,
            min_ev_gap=0.05,
        )

        assert count == 1
        assert filepath
        assert Path(filepath).exists()
        assert meta["skipped_missing_best"] == 0
        line = Path(filepath).read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert json.loads(record["chosen"])["action_id"] == "PLAY|3|"
        assert json.loads(record["rejected"])["action_id"] == "PASS||"

    async def test_skips_missing_best_and_gap(self, decision_service: DecisionService) -> None:
        await decision_service.create_decision_point(
            game_id="game-1",
            round_number=1,
            player_id="p1",
            hand_cards=[3],
            opponent_hands=None,
            last_action=None,
            game_phase="playing",
            legal_actions=[{"id": "PASS||", "action_type": "PASS", "cards": []}],
            chosen_action={"action_type": "PASS", "cards": []},
            action_id="PASS||",
            prompt_messages=_PROMPT,
            ev_loss=0.2,
            evaluator_params={"determinizations": 4},
        )
        await _create_pref_ready(
            decision_service, ev_loss=0.01, round_number=2, best_action_id="PLAY|3|"
        )

        filepath, count, meta = await decision_service.export_preferences(
            train_usable_only=False,
            min_ev_gap=0.05,
        )

        assert count == 0
        assert filepath == ""
        assert meta["skipped_missing_best"] == 1
        assert meta["skipped_gap"] == 1

    async def test_empty_export(self, decision_service: DecisionService) -> None:
        filepath, count, meta = await decision_service.export_preferences()
        assert filepath == ""
        assert count == 0
        assert meta["skipped_missing_best"] == 0
