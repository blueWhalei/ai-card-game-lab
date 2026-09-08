"""EV loss on decision points: storage, filtering, stats, and failure handling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.engine.base import GameAction, GameEngine, GameState
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.eval.rollout import EvaluatorParams
from app.database import init_db
from app.services.decision_eval import DecisionEvaluator
from app.services.decision_service import DecisionService

_FAST = EvaluatorParams(determinizations=1, rollouts_per_world=1, max_candidates=3)


@pytest.fixture
async def decision_service(tmp_path: Path) -> DecisionService:
    db_path = str(tmp_path / "ev.db")
    await init_db(db_path)
    return DecisionService(sqlite_path=db_path, data_dir=str(tmp_path))


async def _create(
    service: DecisionService,
    *,
    decision_ev_loss: float | None,
    game_id: str = "game-1",
    round_number: int = 1,
) -> str:
    return await service.create_decision_point(
        game_id=game_id,
        round_number=round_number,
        player_id="p1",
        hand_cards=[3, 4, 5],
        opponent_hands={"p2": 17},
        last_action=None,
        game_phase="playing",
        legal_actions=[
            {"id": "SINGLE|C3|", "action_type": "SINGLE", "cards": ["C3"]},
            {"id": "PASS||", "action_type": "PASS", "cards": []},
        ],
        chosen_action={"action_type": "SINGLE", "cards": ["C3"]},
        action_id="SINGLE|C3|",
        prompt_messages=[{"role": "user", "content": "pick an action"}],
        thinking="出最小单张",
        ev_loss=decision_ev_loss,
        evaluator_params={"determinizations": 4} if decision_ev_loss is not None else None,
    )


class TestPersistence:
    async def test_ev_loss_round_trips(self, decision_service: DecisionService) -> None:
        decision_id = await _create(decision_service, decision_ev_loss=0.25)

        stored = await decision_service.get_decision_point(decision_id)

        assert stored is not None
        assert stored["ev_loss"] == pytest.approx(0.25)
        assert stored["evaluator_params"] == {"determinizations": 4}

    async def test_policy_kind_round_trips(self, decision_service: DecisionService) -> None:
        decision_id = await decision_service.create_decision_point(
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
            prompt_messages=[{"role": "user", "content": "x"}],
            policy_kind="heuristic",
        )
        stored = await decision_service.get_decision_point(decision_id)
        assert stored is not None
        assert stored["policy_kind"] == "heuristic"

    async def test_unscored_decision_stays_null(
        self, decision_service: DecisionService
    ) -> None:
        """NULL is "not evaluated", which must not read as "gave up nothing"."""
        decision_id = await _create(decision_service, decision_ev_loss=None)

        stored = await decision_service.get_decision_point(decision_id)

        assert stored is not None
        assert stored["ev_loss"] is None
        assert stored["evaluator_params"] is None


class TestFiltering:
    async def test_max_ev_loss_drops_worse_moves(
        self, decision_service: DecisionService
    ) -> None:
        await _create(decision_service, decision_ev_loss=0.1, round_number=1)
        await _create(decision_service, decision_ev_loss=0.9, round_number=2)

        items, total = await decision_service.list_decision_points(max_ev_loss=0.5)

        assert total == 1
        assert items[0]["ev_loss"] == pytest.approx(0.1)

    async def test_max_ev_loss_keeps_unscored_moves(
        self, decision_service: DecisionService
    ) -> None:
        """Otherwise turning the filter on would silently drop all older data."""
        await _create(decision_service, decision_ev_loss=None, round_number=1)
        await _create(decision_service, decision_ev_loss=0.9, round_number=2)

        items, total = await decision_service.list_decision_points(max_ev_loss=0.5)

        assert total == 1
        assert items[0]["ev_loss"] is None

    async def test_export_applies_max_ev_loss(
        self, decision_service: DecisionService
    ) -> None:
        await _create(decision_service, decision_ev_loss=0.1, round_number=1)
        await _create(decision_service, decision_ev_loss=0.9, round_number=2)

        filepath, count, _ = await decision_service.export_chatml(max_ev_loss=0.5)

        assert filepath
        assert count == 1


class TestStats:
    async def test_stats_report_only_scored_decisions(
        self, decision_service: DecisionService
    ) -> None:
        await _create(decision_service, decision_ev_loss=0.2, round_number=1)
        await _create(decision_service, decision_ev_loss=0.8, round_number=2)
        await _create(decision_service, decision_ev_loss=None, round_number=3)

        stats = await decision_service.get_stats()

        assert stats["total"] == 3
        assert stats["evaluated_count"] == 2
        assert stats["avg_ev_loss"] == pytest.approx(0.5)
        assert stats["max_ev_loss"] == pytest.approx(0.8)
        assert stats["blunder_count"] == 1

    async def test_stats_without_any_scores(
        self, decision_service: DecisionService
    ) -> None:
        await _create(decision_service, decision_ev_loss=None)

        stats = await decision_service.get_stats()

        assert stats["evaluated_count"] == 0
        assert stats["avg_ev_loss"] is None
        assert stats["blunder_count"] == 0


class _NoSamplingEngine(DoudizhuEngine):
    """An engine that cannot determinize, like a future engine before it can."""

    @property
    def capability(self) -> Any:
        from dataclasses import replace

        return replace(super().capability, supports_hidden_state_sampling=False)


class _ExplodingEngine(DoudizhuEngine):
    def observe(self, state: GameState, player_id: str) -> Any:
        raise RuntimeError("boom")


class TestDecisionEvaluator:
    def _live_decision(
        self, engine: GameEngine
    ) -> tuple[GameState, str, GameAction]:
        state = engine.initialize(["p1", "p2", "p3"], deal_seed=7)
        player_id = engine.get_current_player(state)
        legal = engine.legal_actions(state, player_id)
        return state, player_id, engine.resolve_action(state, player_id, legal[0].id)

    async def test_scores_a_live_decision(self) -> None:
        engine = DoudizhuEngine()
        state, player_id, action = self._live_decision(engine)

        result = await DecisionEvaluator(_FAST).score(engine, state, player_id, action)

        assert result is not None
        assert result.loss >= 0.0
        assert result.params["determinizations"] == 1

    async def test_returns_none_without_hidden_state_sampling(self) -> None:
        engine = _NoSamplingEngine()
        state, player_id, action = self._live_decision(engine)

        result = await DecisionEvaluator(_FAST).score(engine, state, player_id, action)

        assert result is None

    async def test_a_failing_simulation_does_not_raise(self) -> None:
        """A game must not die because analysis did."""
        engine = _ExplodingEngine()
        base = DoudizhuEngine()
        state = base.initialize(["p1", "p2", "p3"], deal_seed=7)
        player_id = base.get_current_player(state)
        legal = base.legal_actions(state, player_id)
        action = base.resolve_action(state, player_id, legal[0].id)

        result = await DecisionEvaluator(_FAST).score(engine, state, player_id, action)

        assert result is None

    async def test_scoring_is_reproducible(self) -> None:
        engine = DoudizhuEngine()
        state, player_id, action = self._live_decision(engine)
        evaluator = DecisionEvaluator(_FAST)

        first = await evaluator.score(engine, state, player_id, action)
        second = await evaluator.score(engine, state, player_id, action)

        assert first is not None and second is not None
        assert first.loss == pytest.approx(second.loss)

    async def test_the_engine_suggestion_never_scores_worse_than_the_worst_option(
        self,
    ) -> None:
        """Without this the number could be pure noise and every test above still pass."""
        engine = DoudizhuEngine()
        evaluator = DecisionEvaluator(
            EvaluatorParams(determinizations=6, rollouts_per_world=1, max_candidates=8)
        )

        # Bid the highest score available: everyone passing triggers a redeal and
        # bidding never ends. Then compare plays, where options differ in value.
        state = engine.initialize(["p1", "p2", "p3"], deal_seed=7)
        for _ in range(10):
            if str(getattr(state, "phase", "")) != "bidding":
                break
            actor = engine.get_current_player(state)
            legal = engine.legal_actions(state, actor)
            bids = [action for action in legal if action.action.target]
            top = max(bids, key=lambda a: int(a.action.target or 0)) if bids else legal[0]
            state = engine.apply_action(state, engine.resolve_action(state, actor, top.id))
        assert str(getattr(state, "phase", "")) == "playing"
        assert not engine.is_terminal(state)

        player_id = engine.get_current_player(state)
        legal = engine.legal_actions(state, player_id)
        assert len(legal) > 1
        suggested_id = engine.suggest_action(engine.observe(state, player_id), legal)
        assert suggested_id is not None

        losses = {}
        for action_id in (suggested_id, legal[-1].id):
            scored = await evaluator.score(
                engine, state, player_id, engine.resolve_action(state, player_id, action_id)
            )
            assert scored is not None
            losses[action_id] = scored.loss

        assert losses[suggested_id] <= max(losses.values())
