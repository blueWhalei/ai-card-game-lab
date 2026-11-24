"""Compare recorded decision paths; never infer unrecorded state or model reasoning."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def comparison_members(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Use the frozen cohort, never all games from the selected runs."""
    rows = result["experiments"]
    owners = {row["id"] for row in rows}
    coverage = result.get("coverage")
    if not isinstance(coverage, dict) or not isinstance(coverage.get("members"), list):
        raise ValueError("Comparison has no frozen cohort members")
    seeds: set[int] = set()
    games: set[str] = set()
    members = coverage["members"]
    for member in members:
        seed, ids = member["seed"], member["game_ids"]
        if type(seed) is not int or seed in seeds or set(ids) != owners:
            raise ValueError("Invalid frozen cohort membership")
        for row in rows:
            gid = ids[row["id"]]
            if not isinstance(gid, str) or gid in games or gid not in row["game_ids"]:
                raise ValueError("Invalid frozen game identity")
            games.add(gid)
        seeds.add(seed)
    return sorted(members, key=lambda member: member["seed"])


def _action(value: Any) -> tuple[str, tuple[str, ...]]:
    if not isinstance(value, dict) or not isinstance(value.get("action_type"), str):
        raise ValueError("Missing action")
    cards = value.get("cards")
    if not isinstance(cards, list) or not all(isinstance(card, str) for card in cards):
        raise ValueError("Missing cards")
    return value["action_type"], tuple(sorted(cards))


def decision_context(record: dict[str, Any], players: list[str]) -> tuple[Any, ...]:
    """Validated recorded context, normalized by seat; shared with preference export."""
    seat = players.index(record["player_id"])
    hand = record.get("hand_cards")
    counts = record.get("opponent_hands")
    menu = record.get("legal_actions")
    if (
        not isinstance(hand, list)
        or not hand
        or not all(isinstance(card, str) for card in hand)
        or not isinstance(counts, dict)
        or set(counts) != set(players) - {record["player_id"]}
        or any(type(n) is not int or n < 0 for n in counts.values())
        or not isinstance(menu, list)
        or not menu
        or not record.get("game_phase")
        or record.get("parse_fallback") is not False
    ):
        raise ValueError("Incomplete recorded context")
    menu_by_id = {entry["id"]: _action(entry) for entry in menu}
    if (
        len(menu_by_id) != len(menu)
        or not all(isinstance(key, str) and key for key in menu_by_id)
        or menu_by_id.get(record.get("action_id")) != _action(record.get("chosen_action"))
    ):
        raise ValueError("Recorded choice does not match its menu")
    last = record.get("last_action")
    previous = None if last is None else (players.index(last["player"]), _action(last))
    return (
        seat,
        record["game_phase"],
        tuple(sorted(hand)),
        tuple(sorted((players.index(pid), count) for pid, count in counts.items())),
        previous,
        tuple(sorted(menu_by_id.items())),
    )


def _preview(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    try:
        _action(record.get("chosen_action"))
        hand = record.get("hand_cards")
        if not isinstance(hand, list) or not all(isinstance(card, str) for card in hand):
            return None
    except ValueError:
        return None
    return {
        key: record[key]
        for key in (
            "id",
            "game_id",
            "player_id",
            "round_number",
            "game_phase",
            "hand_cards",
            "opponent_hands",
            "last_action",
            "chosen_action",
            "action_id",
        )
    }


def align_decisions(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    seats: list[list[str]],
    totals: list[int],
) -> dict[str, Any]:
    """Only a continuous verified prefix can reach a first action divergence.

    A gap or an invalid record taints the rest of the path; a later matching
    local board does not erase either that uncertainty or a known divergence.
    """
    indexes: list[dict[int, list[dict[str, Any]]]] = []
    for sequence in (left, right):
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for record in sequence:
            grouped[record["round_number"]].append(record)
        indexes.append(grouped)
    turns = range(max(totals))
    frames = []
    path = "same"
    first_divergence: int | None = None
    for turn in turns:
        pair = [index.get(turn, []) for index in indexes]
        records = [items[0] if len(items) == 1 else None for items in pair]
        reasons: list[str] = []
        if any(len(items) > 1 for items in pair):
            reasons.append("duplicate")
        if any(not items for items in pair):
            reasons.append("missing")
        contexts = []
        for point, players in zip(records, seats, strict=True):
            try:
                contexts.append(decision_context(point, players) if point else None)
            except (KeyError, TypeError, ValueError):
                contexts.append(None)
                reasons.append("invalid_context")
        if reasons:
            status = "unverified"
            if path == "same":
                path = "unverified"
        elif path != "same":
            status = "different_path" if path == "diverged" else "unverified"
        elif contexts[0] != contexts[1]:
            status = "different_context"
            path = "unverified"
        elif (
            records[0] is not None
            and records[1] is not None
            and records[0]["action_id"] != records[1]["action_id"]
        ):
            status = "divergence"
            first_divergence = turn
            path = "diverged"
        else:
            status = "same"
        frames.append(
            {
                "turn": turn,
                "status": status,
                "reasons": sorted(set(reasons)),
                "left": _preview(records[0]),
                "right": _preview(records[1]),
                "left_ended": turn >= totals[0],
                "right_ended": turn >= totals[1],
            }
        )
    return {"frames": frames, "first_divergence": first_divergence}
