"""Pick 3–5 post-game highlight moves from stored decision points.

Derived view only — not part of experiment ``protocol``. Reasons are
deterministic so the same game always yields the same list.
"""

from __future__ import annotations

from typing import Any

from app.core.stats.scenarios import classify_scenario

HIGHLIGHT_LIMIT = 5
BRANCH_MIN_LEGAL = 8
_BOMB_ACTIONS = frozenset({"BOMB", "ROCKET"})
REASON_IDS: tuple[str, ...] = ("last_play", "bomb", "fallback", "endgame", "branch")
# Ordinary fills when tagged rows are fewer than three.
FILL_REASON = "play"

# Diversity caps when packing the list (last_play is always at most one).
_TAKE: dict[str, int] = {
    "last_play": 1,
    "bomb": 2,
    "fallback": 2,
    "endgame": 2,
    "branch": 1,
}


def _action_type(point: dict[str, Any]) -> str:
    chosen = point.get("chosen_action")
    if not isinstance(chosen, dict):
        return ""
    return str(chosen.get("action_type") or chosen.get("type") or "").upper()


def _cards(point: dict[str, Any]) -> list[Any]:
    chosen = point.get("chosen_action")
    if not isinstance(chosen, dict):
        return []
    cards = chosen.get("cards")
    return cards if isinstance(cards, list) else []


def _hand_size(point: dict[str, Any]) -> int:
    hand = point.get("hand_cards")
    return len(hand) if isinstance(hand, list) else 0


def _legal_count(point: dict[str, Any]) -> int:
    legal = point.get("legal_actions")
    return len(legal) if isinstance(legal, list) else 0


def _round_number(point: dict[str, Any]) -> int:
    try:
        return int(point.get("round_number") or 0)
    except (TypeError, ValueError):
        return 0


def _reason_for(
    point: dict[str, Any],
    *,
    last_play_id: str | None,
) -> str | None:
    if last_play_id and str(point.get("id") or "") == last_play_id:
        return "last_play"
    action = _action_type(point)
    if action in _BOMB_ACTIONS:
        return "bomb"
    if point.get("parser_ok") is False:
        return "fallback"
    scenario = classify_scenario(
        game_phase=str(point.get("game_phase") or ""),
        hand_size=_hand_size(point),
        action_type=action,
    )
    if scenario == "endgame":
        return "endgame"
    if _legal_count(point) >= BRANCH_MIN_LEGAL:
        return "branch"
    return None


def _last_play_id(points: list[dict[str, Any]], winner_id: str | None) -> str | None:
    if not points:
        return None
    ordered = sorted(points, key=_round_number)
    if winner_id:
        owned = [p for p in ordered if str(p.get("player_id") or "") == winner_id]
        if owned:
            return str(owned[-1].get("id") or "") or None
    return str(ordered[-1].get("id") or "") or None


def _as_highlight(point: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "decision_id": str(point.get("id") or ""),
        "round_number": _round_number(point),
        "player_id": str(point.get("player_id") or ""),
        "reason": reason,
        "action_type": _action_type(point),
        "cards": [str(c) for c in _cards(point)],
        "parser_ok": point.get("parser_ok"),
    }


def pick_game_highlights(
    points: list[dict[str, Any]],
    *,
    winner_id: str | None = None,
    limit: int = HIGHLIGHT_LIMIT,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` highlight rows, chronological.

    Preference order is last play → bomb/rocket → parse fallback → endgame →
    high-branching plays. If that yields fewer than three rows, fill from
    remaining points (latest rounds first).
    """
    cap = max(1, min(int(limit), HIGHLIGHT_LIMIT))
    valid = [p for p in points if p.get("id")]
    if not valid:
        return []

    last_id = _last_play_id(valid, winner_id)
    tagged: list[tuple[str, dict[str, Any]]] = []
    for point in valid:
        reason = _reason_for(point, last_play_id=last_id)
        if reason:
            tagged.append((reason, point))

    by_reason: dict[str, list[dict[str, Any]]] = {key: [] for key in REASON_IDS}
    for reason, point in tagged:
        by_reason[reason].append(point)
    for reason in REASON_IDS:
        by_reason[reason].sort(key=_round_number)

    selected: list[dict[str, Any]] = []
    used: set[str] = set()

    def take(reason: str, n: int) -> None:
        for point in by_reason[reason]:
            if len(selected) >= cap:
                return
            pid = str(point.get("id") or "")
            if not pid or pid in used:
                continue
            selected.append(_as_highlight(point, reason))
            used.add(pid)
            if sum(1 for row in selected if row["reason"] == reason) >= n:
                return

    for reason in REASON_IDS:
        take(reason, _TAKE[reason])

    if len(selected) < min(3, cap, len(valid)):
        rest = sorted(valid, key=_round_number, reverse=True)
        for point in rest:
            if len(selected) >= cap:
                break
            pid = str(point.get("id") or "")
            if not pid or pid in used:
                continue
            reason = _reason_for(point, last_play_id=last_id) or FILL_REASON
            selected.append(_as_highlight(point, reason))
            used.add(pid)

    selected.sort(key=lambda row: int(row["round_number"]))
    return selected[:cap]
