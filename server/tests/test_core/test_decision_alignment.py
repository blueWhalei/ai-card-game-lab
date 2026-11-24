"""Recorded paths must not regain certainty after a gap or a divergence."""

from copy import deepcopy
from typing import Any

import pytest

from app.core.research.decision_alignment import align_decisions, comparison_members


def decision(side: str, turn: int, choice: int = 1) -> dict[str, Any]:
    return {
        "id": f"{side}-{turn}",
        "game_id": side,
        "player_id": f"{side}0",
        "round_number": turn,
        "game_phase": "bidding",
        "hand_cards": ["S3", "H4"],
        "opponent_hands": {f"{side}1": 17, f"{side}2": 17},
        "last_action": None,
        "legal_actions": [{"id": f"BID||{n}", "action_type": "BID", "cards": []} for n in (1, 3)],
        "action_id": f"BID||{choice}",
        "chosen_action": {"action_type": "BID", "cards": []},
        "parse_fallback": False,
    }


def aligned(
    left: list[dict[str, Any]], right: list[dict[str, Any]], totals: list[int] | None = None
) -> dict[str, Any]:
    return align_decisions(
        left, right, [[f"{side}{n}" for n in range(3)] for side in ("a", "b")], totals or [3, 3]
    )


def test_seats_are_normalized_and_bid_targets_remain_distinct() -> None:
    result = aligned(
        [decision("a", n) for n in range(3)],
        [decision("b", n, 3 if n == 1 else 1) for n in range(3)],
    )
    assert [f["status"] for f in result["frames"]] == ["same", "divergence", "different_path"]
    assert result["first_divergence"] == 1
    assert "legal_actions" not in result["frames"][0]["left"]


@pytest.mark.parametrize(
    "damage", ["missing", "duplicate", "fallback", "context", "menu", "seat", "last"]
)
def test_uncertainty_cannot_be_erased_by_later_matching_records(damage: str) -> None:
    left = [decision("a", n) for n in range(3)]
    right = [decision("b", n, 3 if n == 2 else 1) for n in range(3)]
    if damage == "missing":
        right.pop(1)
    elif damage == "duplicate":
        right.append(deepcopy(right[1]))
    elif damage == "fallback":
        right[1]["parse_fallback"] = True
    elif damage == "context":
        right[1]["hand_cards"] = ["S9"]
    elif damage == "menu":
        right[1]["chosen_action"] = {"action_type": "PASS", "cards": []}
    elif damage == "seat":
        right[1]["player_id"] = "unknown"
    else:
        right[1]["last_action"] = {"player": "unknown"}
    result = aligned(left, right)
    assert result["first_divergence"] is None
    assert result["frames"][2]["status"] == "unverified"
    if damage in {"missing", "duplicate"}:
        assert result["frames"][1]["right"] is None
        assert damage in result["frames"][1]["reasons"]


def test_missing_first_frame_and_ended_side_are_explicit() -> None:
    result = aligned([decision("a", 1)], [decision("b", 1), decision("b", 2)], [2, 3])
    assert len(result["frames"]) == 3
    assert result["frames"][0]["left"] is None
    assert result["frames"][0]["right"] is None
    assert result["frames"][1]["status"] == "unverified"
    assert result["frames"][2]["left_ended"] is True
    assert result["frames"][2]["right_ended"] is False


def test_malformed_action_is_not_exposed_as_a_renderable_decision() -> None:
    broken = decision("a", 0)
    broken["chosen_action"] = {}
    result = aligned([broken], [decision("b", 0)], [1, 1])
    assert result["frames"][0]["left"] is None
    assert result["frames"][0]["status"] == "unverified"


def test_only_frozen_members_are_eligible() -> None:
    snapshot = {
        "experiments": [{"id": "a", "game_ids": ["g", "extra"]}],
        "coverage": {"members": [{"seed": 1, "game_ids": {"a": "g"}}]},
    }
    assert comparison_members(snapshot) == [{"seed": 1, "game_ids": {"a": "g"}}]
    snapshot["coverage"]["members"].append({"seed": 2, "game_ids": {"a": "g"}})
    with pytest.raises(ValueError):
        comparison_members(snapshot)
    with pytest.raises(ValueError):
        comparison_members({"experiments": snapshot["experiments"]})
