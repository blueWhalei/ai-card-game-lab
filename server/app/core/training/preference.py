"""Build DPO preference pairs from scored decision points.

Chosen = rollout best action; rejected = what the model actually played.
Pairs are only emitted when ``best_action_id`` was persisted at score time and
the EV gap clears ``min_ev_gap``.
"""

from __future__ import annotations

import json
from typing import Any, Literal

DEFAULT_MIN_EV_GAP = 0.05

SkipReason = Literal["missing_prompt", "missing_best", "missing_action", "tie", "gap"]


def build_preference_pair(
    item: dict[str, Any],
    *,
    min_ev_gap: float = DEFAULT_MIN_EV_GAP,
    include_thinking: bool = False,
) -> tuple[dict[str, Any] | None, SkipReason | None]:
    """Return ``(record, None)`` or ``(None, skip_reason)`` for one decision point."""
    prompt = item.get("prompt_messages")
    if not isinstance(prompt, list) or not prompt:
        return None, "missing_prompt"

    action_id = str(item.get("action_id") or "")
    if not action_id:
        return None, "missing_action"

    params = item.get("evaluator_params")
    if not isinstance(params, dict):
        return None, "missing_best"
    best_action_id = params.get("best_action_id")
    if not isinstance(best_action_id, str) or not best_action_id:
        return None, "missing_best"

    if best_action_id == action_id:
        return None, "tie"

    raw_loss = item.get("ev_loss")
    if raw_loss is None:
        return None, "gap"
    try:
        ev_loss = float(raw_loss)
    except (TypeError, ValueError):
        return None, "gap"
    if ev_loss < min_ev_gap:
        return None, "gap"

    chosen = json.dumps({"action_id": best_action_id}, ensure_ascii=False)
    rejected_payload: dict[str, str] = {"action_id": action_id}
    if include_thinking:
        rejected_payload["thinking"] = str(item.get("thinking") or "")
    rejected = json.dumps(rejected_payload, ensure_ascii=False)

    record = {
        "messages": list(prompt),
        "chosen": chosen,
        "rejected": rejected,
        "metadata": {
            "decision_id": item.get("id"),
            "game_id": item.get("game_id"),
            "round_number": item.get("round_number"),
            "player_id": item.get("player_id"),
            "ev_loss": ev_loss,
            "best_action_id": best_action_id,
            "action_id": action_id,
        },
    }
    return record, None


__all__ = ["DEFAULT_MIN_EV_GAP", "SkipReason", "build_preference_pair"]
