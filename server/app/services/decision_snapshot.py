"""Build decision_points column values from an ``Observation``.

Product column shapes (``hand_cards``, ``opponent_hands``, ``last_action``) live
here so ``AIService`` does not duck-type engine ``GameState`` fields.
"""

from __future__ import annotations

from typing import Any

from app.core.engine.observation import Observation
from app.core.stats.scenarios import classify_game_phase


def hand_cards_from_observation(observation: Observation) -> list[str]:
    raw = observation.private.get("hand_cards") or []
    if not isinstance(raw, list):
        return []
    return [str(card) for card in raw]


def opponent_hands_from_observation(observation: Observation) -> dict[str, int]:
    counts = observation.public.get("hand_counts") or {}
    if not isinstance(counts, dict):
        return {}
    out: dict[str, int] = {}
    for pid, n in counts.items():
        if str(pid) == observation.player_id:
            continue
        out[str(pid)] = int(n)
    return out


def last_action_from_observation(observation: Observation) -> dict[str, Any] | None:
    """Map engine ``public.last_play`` into the Decision UI shape."""
    last_play = observation.public.get("last_play")
    if not isinstance(last_play, dict):
        return None
    return {
        "player": str(last_play.get("player_id") or ""),
        "action_type": str(last_play.get("action_type") or "PASS"),
        "cards": [str(c) for c in (last_play.get("cards") or [])],
    }


def game_phase_from_observation(observation: Observation) -> str:
    counts = observation.public.get("hand_counts") or {}
    sizes: list[int] = []
    if isinstance(counts, dict):
        sizes = [int(n) for n in counts.values()]
    return classify_game_phase(engine_phase=observation.phase, hand_sizes=sizes)
