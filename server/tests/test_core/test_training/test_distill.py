"""Unit tests for distill preference pairing."""

from __future__ import annotations

from app.core.training.distill import (
    build_distill_pair,
    index_decisions_by_match_key,
    pair_distill_indexes,
)


def test_build_distill_pair_happy() -> None:
    teacher = {"id": "t1", "action_id": "A", "game_id": "g1"}
    student = {
        "id": "s1",
        "action_id": "B",
        "game_id": "g2",
        "prompt_messages": [{"role": "user", "content": "hi"}],
        "round_number": 1,
        "_deal_seed": 7,
        "_seat_index": 0,
    }
    record, skip = build_distill_pair(teacher, student)
    assert skip is None
    assert record is not None
    assert '"action_id": "A"' in record["chosen"]
    assert '"action_id": "B"' in record["rejected"]


def test_build_distill_pair_tie() -> None:
    teacher = {"action_id": "A"}
    student = {
        "action_id": "A",
        "prompt_messages": [{"role": "user", "content": "x"}],
    }
    record, skip = build_distill_pair(teacher, student)
    assert record is None
    assert skip == "tie"


def test_pair_indexes_match_and_skip_tie() -> None:
    games = {
        "gt": {
            "id": "gt",
            "player_ids": ["p0", "p1", "p2"],
            "metadata": {"deal_seed": 42},
        },
        "gs": {
            "id": "gs",
            "player_ids": ["q0", "q1", "q2"],
            "metadata": {"deal_seed": 42},
        },
    }
    teacher_items = [
        {
            "id": "td",
            "game_id": "gt",
            "player_id": "p0",
            "round_number": 3,
            "action_id": "PASS",
            "prompt_messages": [{"role": "user", "content": "t"}],
        }
    ]
    student_diff = [
        {
            "id": "sd",
            "game_id": "gs",
            "player_id": "q0",
            "round_number": 3,
            "action_id": "PLAY",
            "prompt_messages": [{"role": "user", "content": "s"}],
        }
    ]
    student_tie = [
        {
            "id": "st",
            "game_id": "gs",
            "player_id": "q0",
            "round_number": 3,
            "action_id": "PASS",
            "prompt_messages": [{"role": "user", "content": "s"}],
        }
    ]
    t_idx, _ = index_decisions_by_match_key(teacher_items, games)
    s_idx, _ = index_decisions_by_match_key(student_diff, games)
    records, meta = pair_distill_indexes(t_idx, s_idx)
    assert len(records) == 1
    assert meta["matched_keys"] == 1

    s_tie, _ = index_decisions_by_match_key(student_tie, games)
    records2, meta2 = pair_distill_indexes(t_idx, s_tie)
    assert records2 == []
    assert meta2["skipped_tie"] == 1
