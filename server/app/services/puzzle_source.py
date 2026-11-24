"""Validate a recorded decision against replay before freezing its stored estimates."""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from app.core.engine.base import GameEngine
from app.core.eval.puzzle import Puzzle, score_answer
from app.core.eval.rollout import EvaluatorParams
from app.services.decision_replay import recorded_states


def recorded_puzzle(
    engine: GameEngine,
    game: dict[str, Any],
    players: list[str],
    seed: int,
    point: dict[str, Any],
    sequence: list[dict[str, Any]],
    rounds: list[dict[str, Any]],
    evaluation: dict[str, Any] | None = None,
) -> Puzzle:
    """Fail closed on any gap or mismatch; do not simulate or repair records."""
    target = point["round_number"]
    if type(target) is not int or not 0 <= target < 2000 or len(sequence) > 2000:
        raise ValueError("Decision sequence exceeds the supported replay range")
    for frame in recorded_states(engine, players, seed, sequence, rounds, target + 1):
        if frame.record["round_number"] == target:
            if frame.record["id"] != point["id"]:
                raise ValueError("Selected decision does not match the recorded sequence")
            observation, legal = frame.observation, frame.legal
            break

    if len(legal) < 2:
        raise ValueError("A choice diagnostic requires at least two legal actions")
    # Batch extraction has its own frozen estimates; source replay stays identical.
    params = evaluation if evaluation is not None else point.get("evaluator_params")
    if not isinstance(params, dict) or not set(EvaluatorParams().to_dict()) <= params.keys():
        raise ValueError("Stored evaluation parameters are incomplete")
    if (
        any(
            type(params[key]) is not int or params[key] <= 0
            for key in ("determinizations", "rollouts_per_world", "max_candidates", "max_steps")
        )
        or type(params["seed"]) is not int
    ):
        raise ValueError("Stored evaluation parameters are invalid")
    values = params.get("action_values")
    legal_ids = {entry.id for entry in legal}
    if (
        not isinstance(values, dict)
        or not values
        or not values.keys() <= legal_ids
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values())
        or params.get("candidates_evaluated") != len(values)
        or params.get("legal_action_count") != len(legal)
        or params.get("truncated") is not (len(values) < len(legal))
    ):
        raise ValueError("Stored action estimates are missing or inconsistent")
    best = params.get("best_action_id")
    if not isinstance(best, str):
        raise ValueError("Stored reference action is missing")
    score_answer(best, values, point["action_id"])
    return Puzzle(
        puzzle_id=f"decision_{point['id']}",
        game_type=engine.game_type,
        source={
            "experiment_id": game["experiment_id"],
            "game_id": game["id"],
            "deal_seed": seed,
            "round_num": target + 1,
            "player_id": point["player_id"],
            "decision_point_id": point["id"],
            "decision_created_at": point["created_at"],
        },
        observation=asdict(observation),
        legal_actions=[
            {"id": entry.id, "label": entry.label, "action": asdict(entry.action)}
            for entry in legal
        ],
        action_values=values,
        best_action_id=best,
        spread=max(values.values()) - min(values.values()),
        candidates_evaluated=len(values),
        legal_action_count=len(legal),
        truncated=len(values) < len(legal),
        evaluator_params=params,
    )
