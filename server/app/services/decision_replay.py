"""Replay a continuous recorded prefix using the existing engine, without inference."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from app.core.engine.base import GameEngine, GameState, LegalAction
from app.core.engine.observation import Observation
from app.core.eval.replay import rebuild_state
from app.core.research.decision_alignment import decision_context
from app.services.decision_snapshot import (
    game_phase_from_observation,
    hand_cards_from_observation,
    last_action_from_observation,
    opponent_hands_from_observation,
)
from app.utils.exceptions import InvalidActionError


@dataclass
class RecordedState:
    record: dict[str, Any]
    state: GameState
    observation: Observation
    legal: list[LegalAction]


def recorded_states(
    engine: GameEngine,
    players: list[str],
    seed: int,
    sequence: list[dict[str, Any]],
    rounds: list[dict[str, Any]],
    total: int,
) -> Iterator[RecordedState]:
    """Yield validated pre-action states; the first invalid step ends the prefix."""
    if type(total) is not int or not 1 <= total <= 2000 or len(sequence) > 2000:
        raise ValueError("Decision sequence exceeds the supported replay range")
    points: dict[int, list[dict[str, Any]]] = defaultdict(list)
    moves: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for point in sequence:
        points[point["round_number"]].append(point)
    for row in rounds:
        moves[row["round_num"]].append(row)
    state = rebuild_state(engine, players, seed, [])
    for turn in range(total):
        if len(points[turn]) != 1 or len(moves[turn + 1]) != 1:
            raise ValueError("Missing or duplicate records before the selected decision")
        record, row = points[turn][0], moves[turn + 1][0]
        actor = engine.get_current_player(state)
        if state.is_terminal or actor != record["player_id"] or actor != row["player_id"]:
            raise ValueError("Recorded actor does not match replay")
        if state.round != record["round_number"]:
            raise ValueError("Recorded turn does not match replay")
        observation = engine.observe(state, actor)
        legal = engine.legal_actions(state, actor)
        chosen = next((entry for entry in legal if entry.id == record["action_id"]), None)
        if chosen is None:
            raise ValueError("Recorded action is not legal in replay")
        replay_record = {
            **record,
            "hand_cards": hand_cards_from_observation(observation),
            "opponent_hands": opponent_hands_from_observation(observation),
            "last_action": last_action_from_observation(observation),
            "game_phase": game_phase_from_observation(observation),
            "legal_actions": [
                {"id": entry.id, "label": entry.label, **asdict(entry.action)} for entry in legal
            ],
            "chosen_action": asdict(chosen.action),
        }
        if decision_context(record, players) != decision_context(replay_record, players):
            raise ValueError("Recorded context does not match replay")
        by_id = {entry.id: entry for entry in legal}
        if any(
            "target" in entry and entry["target"] != by_id[entry["id"]].action.target
            for entry in record["legal_actions"]
        ):
            raise ValueError("Recorded action targets do not match replay")
        if (
            "target" in record["chosen_action"]
            and record["chosen_action"]["target"] != chosen.action.target
        ):
            raise ValueError("Recorded choice target does not match replay")
        cards = json.loads(row["cards"]) if isinstance(row["cards"], str) else row["cards"]
        if row["action_type"] != chosen.action.action_type or sorted(cards or []) != sorted(
            chosen.action.cards or []
        ):
            raise ValueError("Action record disagrees with the decision")
        yield RecordedState(
            record, state, observation, [by_id[entry["id"]] for entry in record["legal_actions"]]
        )
        state = engine.apply_action(state, chosen.action)


def comparison_boards(
    engine: GameEngine,
    players: list[str],
    seed: int,
    sequence: list[dict[str, Any]],
    rounds: list[dict[str, Any]],
    total: int,
    engine_version: str,
) -> dict[str, Any]:
    """Keep verified prefix frames; never fill gaps with guessed or later states."""
    boards: dict[int, Any] = {}
    if engine.capability.engine_version != engine_version:
        return {"frames": boards, "status": "unsupported_engine", "stopped_at": 0}
    try:
        for frame in recorded_states(engine, players, seed, sequence, rounds, total):
            snapshot = engine.get_public_info(frame.state, "observer", is_observer=True)
            boards[frame.state.round] = {"decision_id": frame.record["id"], "snapshot": snapshot}
    except (ValueError, KeyError, TypeError, InvalidActionError):
        return {"frames": boards, "status": "unverified", "stopped_at": len(boards)}
    return {"frames": boards, "status": "verified", "stopped_at": None}
