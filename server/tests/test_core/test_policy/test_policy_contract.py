"""Policy contract tests.

Run every registered policy against every registered engine, so a new policy or
a new engine inherits the same guarantees on arrival.
"""

from __future__ import annotations

import random

import pytest

from app.core.engine.base import GameEngine, GameState
from app.core.policy import get_baseline_policy_registry
from app.core.policy.base import ActionChosen, Budget, PolicyContext
from app.dependencies import get_engine_registry
from app.utils.exceptions import InvalidActionError

_ENGINE_REGISTRY = get_engine_registry()
_ENGINES = [_ENGINE_REGISTRY.get(name) for name in _ENGINE_REGISTRY.list_game_types()]

_POLICY_REGISTRY = get_baseline_policy_registry()
_POLICY_KINDS = _POLICY_REGISTRY.list_kinds()

_CASES = [(engine, kind) for engine in _ENGINES for kind in _POLICY_KINDS]
_CASE_IDS = [f"{engine.game_type}-{kind}" for engine, kind in _CASES]


def _initial_state(engine: GameEngine) -> GameState:
    return engine.initialize([f"p{i}" for i in range(1, engine.min_players + 1)], seed=424242)


def _context(engine: GameEngine, seed: int = 0) -> PolicyContext:
    return PolicyContext(advisor=engine, rng=random.Random(seed), session_id="test")


@pytest.mark.parametrize(("engine", "kind"), _CASES, ids=_CASE_IDS)
async def test_policy_chooses_a_legal_action(engine: GameEngine, kind: str) -> None:
    policy = _POLICY_REGISTRY.create(kind)
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)

    events = [
        event
        async for event in policy.decide(
            engine.observe(state, player_id), legal, Budget(), _context(engine)
        )
    ]

    assert events, "a policy must emit at least one event"
    assert isinstance(events[-1], ActionChosen), "the last event must be the decision"
    chosen = events[-1]
    assert isinstance(chosen, ActionChosen)
    assert chosen.action_id in {action.id for action in legal}
    # The id must round-trip through the engine, not just look plausible.
    engine.resolve_action(state, player_id, chosen.action_id)


@pytest.mark.parametrize(("engine", "kind"), _CASES, ids=_CASE_IDS)
async def test_policy_is_reproducible_for_one_rng_seed(engine: GameEngine, kind: str) -> None:
    policy = _POLICY_REGISTRY.create(kind)
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)
    legal = engine.legal_actions(state, player_id)
    obs = engine.observe(state, player_id)

    first = await policy.decide_action(obs, legal, Budget(), _context(engine, seed=5))
    again = await policy.decide_action(obs, legal, Budget(), _context(engine, seed=5))

    assert first.action_id == again.action_id


@pytest.mark.parametrize(("engine", "kind"), _CASES, ids=_CASE_IDS)
async def test_policy_rejects_an_empty_action_list(engine: GameEngine, kind: str) -> None:
    policy = _POLICY_REGISTRY.create(kind)
    state = _initial_state(engine)
    obs = engine.observe(state, engine.get_current_player(state))

    with pytest.raises(InvalidActionError):
        await policy.decide_action(obs, [], Budget(), _context(engine))


@pytest.mark.parametrize(("engine", "kind"), _CASES, ids=_CASE_IDS)
async def test_policy_can_drive_a_full_game(engine: GameEngine, kind: str) -> None:
    """A whole game with no LLM in the loop -- what makes CI able to run games."""
    policy = _POLICY_REGISTRY.create(kind)
    state = _initial_state(engine)
    ctx = _context(engine, seed=17)

    for _ in range(500):
        if engine.is_terminal(state):
            break
        player_id = engine.get_current_player(state)
        legal = engine.legal_actions(state, player_id)
        chosen = await policy.decide_action(engine.observe(state, player_id), legal, Budget(), ctx)
        state = engine.apply_action(
            state, engine.resolve_action(state, player_id, chosen.action_id)
        )
    else:
        pytest.fail("policy did not finish a game within the step budget")

    rewards = engine.terminal_rewards(state)
    assert set(rewards) == set(state.player_ids)


def test_registry_rejects_an_unknown_kind() -> None:
    with pytest.raises(InvalidActionError):
        _POLICY_REGISTRY.create("no_such_policy")


def test_registry_lists_the_baselines() -> None:
    assert set(_POLICY_KINDS) == {"random", "first", "heuristic"}


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_engine_suggestions_are_legal(engine: GameEngine) -> None:
    """Whatever the house heuristic returns must be one of the offered actions."""
    state = _initial_state(engine)

    for _ in range(200):
        if engine.is_terminal(state):
            break
        player_id = engine.get_current_player(state)
        legal = engine.legal_actions(state, player_id)
        suggestion = engine.suggest_action(engine.observe(state, player_id), legal)

        if suggestion is not None:
            assert suggestion in {action.id for action in legal}
            chosen = engine.resolve_action(state, player_id, suggestion)
        else:
            chosen = legal[0].action
        state = engine.apply_action(state, chosen)
