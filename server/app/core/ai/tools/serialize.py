"""Serialize tool dataclasses for traces, WebSocket, and decision explain."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def _as_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return None


def compact_hand_analysis(value: Any) -> dict[str, Any] | None:
    raw = _as_dict(value)
    if not raw:
        return None
    return {
        "bomb_count": int(raw.get("bomb_count") or 0),
        "rocket": bool(raw.get("rocket")),
        "strength_score": float(raw.get("strength_score") or 0.0),
    }


def compact_win_probability(value: Any) -> dict[str, Any] | None:
    raw = _as_dict(value)
    if not raw:
        return None
    probability = raw.get("probability")
    return {
        "probability": float(probability) if probability is not None else 0.5,
        "confidence": str(raw.get("confidence") or ""),
        "reasoning": str(raw.get("reasoning") or ""),
        "factors": list(raw.get("factors") or []),
    }


def explain_from_tools(tool_results: dict[str, Any] | None) -> dict[str, Any]:
    """Subset of tool output safe to put on WS / traces / decision explain."""
    if not tool_results:
        return {}
    payload: dict[str, Any] = {}
    win = compact_win_probability(tool_results.get("win_probability"))
    if win:
        payload["win_probability"] = win
    hand = compact_hand_analysis(tool_results.get("hand_analysis"))
    if hand:
        payload["hand_analysis"] = hand
    return payload


def actions_as_dicts(actions: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions:
        out.append(
            {
                "action_type": str(getattr(action, "action_type", "")),
                "cards": list(getattr(action, "cards", None) or []),
            }
        )
    return out
