"""Build decision_points column values from an ``Observation``.

Product column shapes (``hand_cards``, ``opponent_hands``, ``last_action``) live
here so ``AIService`` does not duck-type engine ``GameState`` fields.
"""

from __future__ import annotations

from typing import Any

from app.core.engine.base import GameAction, GameEngine, LegalAction
from app.core.engine.observation import Observation
from app.core.stats.scenarios import classify_game_phase

# Trace payload keys → engine tool names for the stored summary.
_TRACE_KEY_TO_TOOL: dict[str, str] = {
    "hand_analysis": "analyze_hand",
    "win_probability": "win_probability",
}


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


def compact_tool_calls(tool_results: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Compress in-memory tool results for ``decision_points.tool_calls``."""
    if not tool_results:
        return None
    out: list[dict[str, Any]] = []
    for key, value in tool_results.items():
        if key == "tool_analysis":
            continue
        name = _TRACE_KEY_TO_TOOL.get(key, str(key))
        entry: dict[str, Any] = {"name": name}
        if isinstance(value, dict):
            entry["keys"] = [str(k) for k in value if k != "text"]
            text = value.get("text")
            if isinstance(text, str) and text.strip():
                entry["has_text"] = True
        out.append(entry)
    return out or None


def observation_from_decision_point(point: dict[str, Any], game_type: str) -> Observation:
    """Rebuild a minimal ``Observation`` for offline baseline suggestions."""
    player_id = str(point.get("player_id") or "")
    hand_raw = point.get("hand_cards") or []
    hand = [str(c) for c in hand_raw] if isinstance(hand_raw, list) else []
    counts: dict[str, int] = {player_id: len(hand)} if player_id else {}
    opponents = point.get("opponent_hands") or {}
    if isinstance(opponents, dict):
        for pid, n in opponents.items():
            counts[str(pid)] = int(n)
    last = point.get("last_action")
    last_play: dict[str, Any] | None = None
    if isinstance(last, dict):
        last_play = {
            "player_id": str(last.get("player") or last.get("player_id") or ""),
            "action_type": str(last.get("action_type") or "PASS"),
            "cards": [str(c) for c in (last.get("cards") or [])],
            "power": 0,
        }
    stored_phase = str(point.get("game_phase") or "playing")
    engine_phase = "bidding" if stored_phase == "bidding" else "playing"
    return Observation(
        game_type=game_type,
        phase=engine_phase,
        round=int(point.get("round_number") or 0),
        player_id=player_id,
        to_act=True,
        private={"hand_cards": hand},
        public={
            "hand_counts": counts,
            "last_play": last_play,
            "consecutive_passes": 0,
            "roles": {},
            "player_ids": list(counts.keys()),
        },
    )


def legal_actions_from_decision_point(point: dict[str, Any]) -> list[LegalAction]:
    """Rebuild the presented menu from stored legal_actions JSON."""
    player_id = str(point.get("player_id") or "")
    raw = point.get("legal_actions") or []
    if not isinstance(raw, list):
        return []
    result: list[LegalAction] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        action_id = str(entry.get("id") or "")
        if not action_id:
            continue
        cards_raw = entry.get("cards") or []
        cards = [str(c) for c in cards_raw] if isinstance(cards_raw, list) else []
        target = entry.get("target")
        action = GameAction(
            player_id=player_id,
            action_type=str(entry.get("action_type") or "PASS"),
            cards=cards,
            target=str(target) if target is not None else None,
        )
        result.append(
            LegalAction(
                id=action_id,
                label=str(entry.get("label") or action_id),
                action=action,
            )
        )
    return result


def baseline_suggestion_for_point(
    point: dict[str, Any],
    engine: GameEngine,
) -> tuple[str | None, str | None]:
    """Return ``(action_id, label)`` from the engine house heuristic, or ``(None, None)``."""
    legal = legal_actions_from_decision_point(point)
    if not legal:
        return None, None
    try:
        observation = observation_from_decision_point(point, engine.game_type)
        suggested = engine.suggest_action(observation, legal)
    except Exception:
        return None, None
    if not suggested:
        return None, None
    label = next((la.label for la in legal if la.id == suggested), suggested)
    return str(suggested), str(label)
