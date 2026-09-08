"""Engine contract tests.

Every registered engine must satisfy these invariants, so a second engine
inherits the same guarantees the moment it is registered.
"""

from __future__ import annotations

import json
import random

import pytest

from app.core.engine.base import GameEngine, GameState
from app.dependencies import get_engine_registry
from app.utils.exceptions import InvalidActionError

_REGISTRY = get_engine_registry()
_ENGINES = [_REGISTRY.get(game_type) for game_type in _REGISTRY.list_game_types()]


def _player_ids(engine: GameEngine) -> list[str]:
    return [f"p{i}" for i in range(1, engine.min_players + 1)]


def _initial_state(engine: GameEngine) -> GameState:
    return engine.initialize(_player_ids(engine), seed=20260906)


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_legal_action_ids_are_unique(engine: GameEngine) -> None:
    state = _initial_state(engine)
    actions = engine.legal_actions(state, engine.get_current_player(state))

    assert actions, "engine must offer at least one legal action at game start"
    ids = [a.id for a in actions]
    assert len(ids) == len(set(ids))
    assert all(a.id and a.label for a in actions)


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_resolve_action_round_trips(engine: GameEngine) -> None:
    state = _initial_state(engine)
    player_id = engine.get_current_player(state)

    for legal in engine.legal_actions(state, player_id):
        assert engine.resolve_action(state, player_id, legal.id) == legal.action


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_resolve_action_rejects_unknown_id(engine: GameEngine) -> None:
    state = _initial_state(engine)

    with pytest.raises(InvalidActionError):
        engine.resolve_action(state, engine.get_current_player(state), "NOPE|not-a-card|")


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_legal_actions_are_reproducible(engine: GameEngine) -> None:
    """Same seed, same state -> identical ids in identical order."""
    first = engine.legal_actions(_initial_state(engine), "p1")
    second = engine.legal_actions(_initial_state(engine), "p1")

    assert [a.id for a in first] == [a.id for a in second]
    assert [a.label for a in first] == [a.label for a in second]


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_action_ids_survive_a_full_game(engine: GameEngine) -> None:
    """Ids stay resolvable at every decision of a complete game."""
    state = _play_to_terminal(engine)

    assert engine.is_terminal(state)


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_terminal_rewards_rejects_unfinished_game(engine: GameEngine) -> None:
    with pytest.raises(InvalidActionError):
        engine.terminal_rewards(_initial_state(engine))


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_terminal_rewards_cover_every_player(engine: GameEngine) -> None:
    state = _play_to_terminal(engine)
    rewards = engine.terminal_rewards(state)

    assert set(rewards) == set(state.player_ids)
    assert all(isinstance(value, float) for value in rewards.values())
    if engine.get_winner(state) is not None:
        assert rewards[engine.get_winner(state)] > 0.0


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_observation_is_scoped_to_the_viewer(engine: GameEngine) -> None:
    state = _initial_state(engine)
    players = _player_ids(engine)

    for player_id in players:
        obs = engine.observe(state, player_id)
        assert obs.game_type == engine.game_type
        assert obs.player_id == player_id
        assert obs.to_act == (engine.get_current_player(state) == player_id)
        assert obs.text

    others = players[1:]
    leaked = [
        pid
        for pid in others
        if engine.observe(state, players[0]).private == engine.observe(state, pid).private
    ]
    assert not leaked, "private sections must differ per viewer"


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_hidden_state_sampling_matches_capability(engine: GameEngine) -> None:
    state = _initial_state(engine)
    obs = engine.observe(state, engine.get_current_player(state))

    if not engine.capability.supports_hidden_state_sampling:
        with pytest.raises(InvalidActionError):
            engine.sample_hidden_state(obs, random.Random(1))
        return

    sampled = engine.sample_hidden_state(obs, random.Random(1))

    assert sampled.game_type == engine.game_type
    assert sampled.player_ids == state.player_ids
    assert not engine.is_terminal(sampled)
    # The viewer keeps a full set of legal actions in the sampled world.
    assert engine.legal_actions(sampled, obs.player_id)


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_hidden_state_sampling_varies_with_the_rng(engine: GameEngine) -> None:
    if not engine.capability.supports_hidden_state_sampling:
        pytest.skip("engine does not sample hidden state")

    state = _initial_state(engine)
    obs = engine.observe(state, engine.get_current_player(state))

    first = engine.sample_hidden_state(obs, random.Random(1))
    same_seed = engine.sample_hidden_state(obs, random.Random(1))
    other_seed = engine.sample_hidden_state(obs, random.Random(2))

    assert first == same_seed, "same rng seed must reproduce the same world"
    assert first != other_seed, "a different seed must produce a different world"


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_declared_tools_are_callable_and_json_safe(engine: GameEngine) -> None:
    state = _initial_state(engine)
    obs = engine.observe(state, engine.get_current_player(state))

    for tool in engine.capability.tools:
        assert tool.name and tool.description
        assert tool.parameters.get("type") == "object"

        result = engine.run_tool(tool.name, obs)
        assert isinstance(result, dict)
        json.dumps(result)  # policies forward tool results as JSON

    published = engine.capability.to_public_dict()
    json.dumps(published)
    assert [t["name"] for t in published["tools"]] == [t.name for t in engine.capability.tools]


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.game_type)
def test_unknown_tool_is_rejected(engine: GameEngine) -> None:
    state = _initial_state(engine)
    obs = engine.observe(state, engine.get_current_player(state))

    with pytest.raises(InvalidActionError):
        engine.run_tool("no_such_tool", obs)


def _play_to_terminal(engine: GameEngine, *, budget: int = 500) -> GameState:
    """Drive a game to the end by always taking the first legal action."""
    state = _initial_state(engine)

    for _ in range(budget):
        if engine.is_terminal(state):
            return state
        player_id = engine.get_current_player(state)
        actions = engine.legal_actions(state, player_id)
        assert actions
        chosen = actions[0]
        assert engine.resolve_action(state, player_id, chosen.id) == chosen.action
        state = engine.apply_action(state, chosen.action)

    pytest.fail("game did not reach a terminal state within the step budget")
