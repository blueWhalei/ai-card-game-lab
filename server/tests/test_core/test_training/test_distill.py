"""Preferences require a verified shared history, not just equal round numbers."""

from copy import deepcopy
from typing import Any

import pytest

from app.core.training.distill import build_distill_pair, pair_distill_decisions
from tests.test_core.test_decision_alignment import decision


def sample(side: str, turn: int, choice: int = 1) -> dict[str, Any]:
    return {
        **decision(side, turn, choice),
        "prompt_messages": [{"role": "user", "content": "Choose a legal action"}],
    }


def games(side: str) -> dict[str, dict[str, Any]]:
    return {
        side: {
            "id": side,
            "game_type": "doudizhu",
            "status": "finished",
            "total_rounds": 3,
            "player_ids": [f"{side}{i}" for i in range(3)],
            "metadata": {"deal_seed": 7},
        }
    }


def test_export_only_first_divergence_and_not_later_matching_context() -> None:
    teachers = [sample("a", n) for n in range(3)]
    students = [sample("b", n, 3 if n > 0 else 1) for n in range(3)]
    pairs, meta = pair_distill_decisions(teachers, students, games("a"), games("b"))
    assert len(pairs) == 1
    assert pairs[0]["metadata"]["round_number"] == 1
    assert pairs[0]["metadata"]["preference_source"] == "teacher_choice"
    assert meta["skipped_tie"] == 1 and meta["skipped_different_path"] == 1


@pytest.mark.parametrize(
    "damage", ["missing", "duplicate", "fallback", "hand", "illegal", "missing_prompt"]
)
def test_damaged_history_or_choice_cannot_create_a_preference(damage: str) -> None:
    teachers = [sample("a", n) for n in range(3)]
    students = [sample("b", n, 3 if n == 2 else 1) for n in range(3)]
    if damage == "missing":
        teachers.pop(0)
    elif damage == "duplicate":
        teachers.append(deepcopy(teachers[0]))
    elif damage == "fallback":
        teachers[0]["parse_fallback"] = True
    elif damage == "hand":
        teachers[0]["hand_cards"] = ["S9"]
    elif damage == "illegal":
        teachers[2]["action_id"] = "UNAVAILABLE"
    else:
        students[2]["prompt_messages"] = []
    pairs, meta = pair_distill_decisions(teachers, students, games("a"), games("b"))
    assert pairs == []
    assert meta["skipped_invalid_context"] or meta["skipped_missing_prompt"]


def test_duplicate_deal_is_excluded_even_when_duplicate_has_no_decisions() -> None:
    source = games("a")
    source["retry"] = {**source["a"], "id": "retry", "status": "failed"}
    pairs, meta = pair_distill_decisions([sample("a", 0)], [sample("b", 0, 3)], source, games("b"))
    assert pairs == [] and meta["skipped_duplicate_seed"] == 1


def test_local_pair_builder_rejects_illegal_teacher_and_mismatched_menu() -> None:
    teacher, student = sample("a", 0), sample("b", 0, 3)
    seats = [games(side)[side]["player_ids"] for side in ("a", "b")]
    record, skip = build_distill_pair(teacher, student, seats=seats)
    assert record is not None and skip is None
    teacher["action_id"] = "illegal"
    assert build_distill_pair(teacher, student, seats=seats) == (None, "invalid_context")
