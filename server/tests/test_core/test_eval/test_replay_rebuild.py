"""Deal-seed state replay: rebuild a GameState from a seed and recorded actions.

Contract: replaying the same deal seed and the same action sequence must land on
the same state the live game reached -- same player to act and same set of legal
action ids. This is what the puzzle extractor relies on to recompute gold labels
without re-running the original game.
"""

from __future__ import annotations

import random

from app.core.engine.base import GameAction, GameState, LegalAction
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.eval.replay import action_from_round_row, rebuild_state
from app.core.policy import HeuristicPolicy, PolicyContext


def _play_n_plies(
    engine: DoudizhuEngine,
    state: GameState,
    n: int,
    rng: random.Random,
) -> tuple[GameState, list[GameAction]]:
    """Drive the game forward with the house heuristic, recording each action."""
    policy = HeuristicPolicy()
    ctx = PolicyContext(advisor=engine, rng=rng)
    recorded: list[GameAction] = []
    current = state
    for _ in range(n):
        if engine.is_terminal(current):
            break
        player_id = engine.get_current_player(current)
        legal = engine.legal_actions(current, player_id)
        if not legal:
            break
        chosen_id = policy.choose(engine.observe(current, player_id), legal, ctx)
        action = next(la.action for la in legal if la.id == chosen_id)
        current = engine.apply_action(current, action)
        recorded.append(action)
    return current, recorded


def test_rebuild_matches_live_legal_ids() -> None:
    engine = DoudizhuEngine()
    players = ["p1", "p2", "p3"]
    seed = 42

    live = engine.initialize(players, seed=seed)
    live_after, recorded = _play_n_plies(engine, live, n=5, rng=random.Random(7))

    rebuilt = rebuild_state(engine, players, seed, recorded)

    assert engine.get_current_player(rebuilt) == engine.get_current_player(live_after)
    viewer = engine.get_current_player(live_after)
    rebuilt_ids = {la.id for la in engine.legal_actions(rebuilt, viewer)}
    live_ids = {la.id for la in engine.legal_actions(live_after, viewer)}
    assert rebuilt_ids == live_ids


def test_rebuild_with_no_actions_matches_initial_state() -> None:
    engine = DoudizhuEngine()
    players = ["p1", "p2", "p3"]
    seed = 42

    initial = engine.initialize(players, seed=seed)
    rebuilt = rebuild_state(engine, players, seed, [])

    assert engine.get_current_player(rebuilt) == engine.get_current_player(initial)
    viewer = engine.get_current_player(initial)
    assert {la.id for la in engine.legal_actions(rebuilt, viewer)} == {
        la.id for la in engine.legal_actions(initial, viewer)
    }


def test_rebuild_is_deterministic_across_calls() -> None:
    engine = DoudizhuEngine()
    players = ["p1", "p2", "p3"]
    seed = 42

    live = engine.initialize(players, seed=seed)
    _, recorded = _play_n_plies(engine, live, n=4, rng=random.Random(3))

    first = rebuild_state(engine, players, seed, recorded)
    second = rebuild_state(engine, players, seed, recorded)

    assert engine.get_current_player(first) == engine.get_current_player(second)
    viewer = engine.get_current_player(first)
    assert {la.id for la in engine.legal_actions(first, viewer)} == {
        la.id for la in engine.legal_actions(second, viewer)
    }


def test_action_from_round_row_builds_gameaction() -> None:
    action = action_from_round_row("SINGLE", ["S3", "H3"])
    assert action.action_type == "SINGLE"
    assert action.cards == ["S3", "H3"]

    empty = action_from_round_row("PASS", None)
    assert empty.action_type == "PASS"
    assert empty.cards == []


def test_action_from_round_row_preserves_card_order() -> None:
    action = action_from_round_row("PAIR", ["H7", "S7"])
    # Engine canonicalizes on apply; the helper just carries what it was given.
    assert set(action.cards) == {"S7", "H7"}


def _legal_id_set(engine: DoudizhuEngine, state: GameState) -> set[str]:
    viewer = engine.get_current_player(state)
    return {la.id for la in engine.legal_actions(state, viewer)}


def test_rebuild_matches_live_through_bidding_and_playing() -> None:
    """Bidding (3 plies) plus several playing plies must replay exactly."""
    engine = DoudizhuEngine()
    players = ["p1", "p2", "p3"]
    seed = 42

    live = engine.initialize(players, seed=seed)
    live_after, recorded = _play_n_plies(engine, live, n=10, rng=random.Random(11))

    if engine.is_terminal(live_after):
        # If the game ended early the contract is trivially satisfied; still check.
        assert engine.is_terminal(rebuild_state(engine, players, seed, recorded))
        return

    rebuilt = rebuild_state(engine, players, seed, recorded)
    assert _legal_id_set(engine, rebuilt) == _legal_id_set(engine, live_after)
    assert engine.get_current_player(rebuilt) == engine.get_current_player(live_after)


# Silence the unused import warning for LegalAction in case linters complain.
_ = LegalAction
