"""Rollout evaluator tests.

The generic invariants run against every engine that supports determinization;
the value assertions use Doudizhu states where the right answer is obvious.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.engine.base import EngineCapability, GameEngine, GameState
from app.core.engine.doudizhu.cards import ActionType
from app.core.engine.doudizhu.engine import DoudizhuEngine, DoudizhuState
from app.core.engine.doudizhu.hand_evaluator import classify
from app.core.eval import EvaluatorParams, RolloutEvaluator
from app.core.policy import HeuristicPolicy, RandomPolicy
from app.dependencies import get_engine_registry
from app.utils.exceptions import InvalidActionError

_REGISTRY = get_engine_registry()
_SAMPLING_ENGINES = [
    engine
    for engine in (_REGISTRY.get(name) for name in _REGISTRY.list_game_types())
    if engine.capability.supports_hidden_state_sampling
]

# Small on purpose: these tests check contracts, not statistical strength.
_FAST = EvaluatorParams(determinizations=2, max_candidates=3, seed=11)


def _initial_state(engine: GameEngine) -> GameState:
    return engine.initialize([f"p{i}" for i in range(1, engine.min_players + 1)], seed=99)


def _evaluator(engine: GameEngine, params: EvaluatorParams = _FAST) -> RolloutEvaluator:
    return RolloutEvaluator(engine, RandomPolicy(), params)


@pytest.mark.parametrize("engine", _SAMPLING_ENGINES, ids=lambda e: e.game_type)
def test_ev_loss_is_never_negative(engine: GameEngine) -> None:
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)

    result = _evaluator(engine).ev_loss(engine.observe(state, player_id), legal, legal[-1].id)

    assert result.loss >= 0.0
    assert result.best_value >= result.chosen_value


@pytest.mark.parametrize("engine", _SAMPLING_ENGINES, ids=lambda e: e.game_type)
def test_the_action_under_review_is_always_evaluated(engine: GameEngine) -> None:
    """Truncating candidates must never drop the move we were asked about."""
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)
    assert len(legal) > _FAST.max_candidates

    result = _evaluator(engine).ev_loss(engine.observe(state, player_id), legal, legal[-1].id)

    assert legal[-1].id in result.values
    assert result.candidates_evaluated <= _FAST.max_candidates
    assert result.truncated


@pytest.mark.parametrize("engine", _SAMPLING_ENGINES, ids=lambda e: e.game_type)
def test_the_best_candidate_has_zero_loss(engine: GameEngine) -> None:
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)
    obs = engine.observe(state, player_id)
    evaluator = _evaluator(engine)

    values = evaluator.action_values(obs, legal)
    best = max(values, key=lambda action_id: values[action_id])

    assert evaluator.ev_loss(obs, legal, best).loss == pytest.approx(0.0)


@pytest.mark.parametrize("engine", _SAMPLING_ENGINES, ids=lambda e: e.game_type)
def test_values_are_reproducible_for_one_seed(engine: GameEngine) -> None:
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)
    obs = engine.observe(state, player_id)

    same = EvaluatorParams(determinizations=2, max_candidates=3, seed=7)
    other = EvaluatorParams(determinizations=2, max_candidates=3, seed=8)

    first = _evaluator(engine, same).action_values(obs, legal)
    again = _evaluator(engine, same).action_values(obs, legal)
    different = _evaluator(engine, other).action_values(obs, legal)

    assert first == again
    assert first != different


@pytest.mark.parametrize("engine", _SAMPLING_ENGINES, ids=lambda e: e.game_type)
def test_illegal_choice_is_rejected(engine: GameEngine) -> None:
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)

    with pytest.raises(InvalidActionError):
        _evaluator(engine).ev_loss(engine.observe(state, player_id), legal, "NOPE|nothing|")


@pytest.mark.parametrize("engine", _SAMPLING_ENGINES, ids=lambda e: e.game_type)
def test_params_travel_with_the_result(engine: GameEngine) -> None:
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)

    result = _evaluator(engine).ev_loss(engine.observe(state, player_id), legal, legal[0].id)

    assert result.params == _FAST.to_dict()


def test_evaluator_refuses_an_engine_that_cannot_sample() -> None:
    class Blind(DoudizhuEngine):
        @property
        def capability(self) -> EngineCapability:
            return replace(super().capability, supports_hidden_state_sampling=False)

    with pytest.raises(InvalidActionError):
        RolloutEvaluator(Blind(), RandomPolicy())


def _winning_state() -> DoudizhuState:
    """p1 can empty its hand this turn; everyone else still holds cards."""
    return DoudizhuState(
        game_type="doudizhu",
        round=20,
        player_ids=["p1", "p2", "p3"],
        current_player="p1",
        is_terminal=False,
        hands={"p1": ["S6", "H6"], "p2": ["S9", "H9"], "p3": ["SJ", "HJ"]},
        roles={"p1": "landlord", "p2": "peasant", "p3": "peasant"},
        landlord_cards=[],
        last_play=None,
        consecutive_passes=0,
        play_history=[],
        turn_order=["p1", "p2", "p3"],
        current_turn_index=0,
        phase="playing",
    )


def test_a_winning_move_is_worth_the_full_payoff() -> None:
    engine = DoudizhuEngine()
    state = _winning_state()
    legal = engine.legal_actions(state, "p1")
    pair = next(a for a in legal if a.action.action_type == ActionType.PAIR)

    values = RolloutEvaluator(engine, RandomPolicy(), _FAST).action_values(
        engine.observe(state, "p1"), legal, must_include=pair.id
    )

    assert values[pair.id] == pytest.approx(1.0)


def test_bombing_beats_passing_when_an_opponent_is_one_move_from_winning() -> None:
    engine = DoudizhuEngine()
    single_seven = classify(["S7"])
    assert single_seven is not None
    state = DoudizhuState(
        game_type="doudizhu",
        round=18,
        player_ids=["p1", "p2", "p3"],
        current_player="p1",
        is_terminal=False,
        hands={"p1": ["S6", "H6", "D6", "C6"], "p2": ["S9"], "p3": ["SJ", "HJ"]},
        roles={"p1": "landlord", "p2": "peasant", "p3": "peasant"},
        landlord_cards=[],
        last_play=("p2", single_seven[0], single_seven[1], ["S7"]),
        consecutive_passes=0,
        play_history=[{"round": 17, "player_id": "p2", "action_type": "SINGLE", "cards": ["S7"]}],
        turn_order=["p1", "p2", "p3"],
        current_turn_index=0,
        phase="playing",
    )
    legal = engine.legal_actions(state, "p1")
    bomb = next(a for a in legal if a.action.action_type == ActionType.BOMB)
    keep_passing = next(a for a in legal if a.action.action_type == ActionType.PASS)

    values = RolloutEvaluator(
        engine, HeuristicPolicy(), EvaluatorParams(determinizations=4, seed=3)
    ).action_values(engine.observe(state, "p1"), legal)

    assert values[bomb.id] > values[keep_passing.id]
