"""Unit tests for puzzle presentation perturbations."""

from __future__ import annotations

import random

import pytest

from app.core.eval.perturb import DEFAULT_PERTURB_KINDS, perturb_puzzle
from app.core.eval.puzzle import Puzzle


def _sample_puzzle() -> Puzzle:
    return Puzzle(
        puzzle_id="pz_t",
        game_type="doudizhu",
        source={"game_id": "g1"},
        observation={
            "game_type": "doudizhu",
            "phase": "playing",
            "round": 1,
            "player_id": "p1",
            "to_act": True,
            "private": {"hand_cards": ["3", "4", "5", "6"]},
            "public": {
                "play_history": [{"player_id": "p2", "cards": ["7"]}],
                "turn_order": ["p1", "p2", "p3"],
            },
            "text": "frozen",
        },
        legal_actions=[
            {"id": "a", "label": "a", "action": {"action_type": "PASS", "cards": []}},
            {"id": "b", "label": "b", "action": {"action_type": "PLAY", "cards": ["3"]}},
            {"id": "c", "label": "c", "action": {"action_type": "PLAY", "cards": ["4"]}},
        ],
        action_values={"a": 0.1, "b": 0.9, "c": 0.2},
        best_action_id="b",
        spread=0.8,
        candidates_evaluated=3,
        legal_action_count=3,
        truncated=False,
    )


def test_shuffle_legal_actions_preserves_ids_and_gold() -> None:
    original = _sample_puzzle()
    orig_ids = [row["id"] for row in original.legal_actions]
    pert = None
    for seed in range(50):
        candidate = perturb_puzzle(original, ["shuffle_legal_actions"], random.Random(seed))
        if [row["id"] for row in candidate.legal_actions] != orig_ids:
            pert = candidate
            break
    assert pert is not None, "expected some seed to reorder three legal actions"
    assert {row["id"] for row in pert.legal_actions} == {"a", "b", "c"}
    assert pert.best_action_id == "b"
    assert pert.action_values == original.action_values
    assert [row["id"] for row in original.legal_actions] == orig_ids


def test_shuffle_hand_cards_preserves_multiset_and_forbidden_fields() -> None:
    original = _sample_puzzle()
    history_before = list(original.observation["public"]["play_history"])
    turn_before = list(original.observation["public"]["turn_order"])
    hand_before = list(original.observation["private"]["hand_cards"])
    pert = None
    for seed in range(50):
        candidate = perturb_puzzle(original, ["shuffle_hand_cards"], random.Random(seed))
        if candidate.observation["private"]["hand_cards"] != hand_before:
            pert = candidate
            break
    assert pert is not None
    assert sorted(pert.observation["private"]["hand_cards"]) == sorted(hand_before)
    assert pert.observation["public"]["play_history"] == history_before
    assert pert.observation["public"]["turn_order"] == turn_before
    assert pert.observation["text"] == "frozen"


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        perturb_puzzle(
            _sample_puzzle(),
            ["shuffle_legal_actions", "nope"],  # type: ignore[list-item]
            random.Random(0),
        )


def test_default_kinds_tuple() -> None:
    assert "shuffle_legal_actions" in DEFAULT_PERTURB_KINDS
    assert "shuffle_hand_cards" in DEFAULT_PERTURB_KINDS


def test_zh_en_labels_keeps_ids() -> None:
    original = _sample_puzzle()
    original.legal_actions = [
        {"id": "a", "label": "不出", "action": {"action_type": "PASS", "cards": []}},
        {"id": "b", "label": "单张", "action": {"action_type": "SINGLE", "cards": ["3"]}},
    ]
    pert = perturb_puzzle(original, ["zh_en_labels"], random.Random(0))
    assert [row["id"] for row in pert.legal_actions] == ["a", "b"]
    assert pert.legal_actions[0]["label"] == "Pass"
    assert pert.best_action_id == original.best_action_id


def test_card_symbol_style_preserves_gold() -> None:
    original = _sample_puzzle()
    original.observation["private"]["hand_cards"] = ["C3", "D5"]
    pert = perturb_puzzle(original, ["card_symbol_style"], random.Random(0))
    assert pert.observation["private"]["hand_cards"] == ["C③", "D⑤"]
    assert pert.best_action_id == "b"
    assert [row["id"] for row in pert.legal_actions] == ["a", "b", "c"]


def test_rotate_seats_cycles_ids_keeps_action_gold() -> None:
    original = _sample_puzzle()
    pert = perturb_puzzle(original, ["rotate_seats"], random.Random(0))
    assert pert.observation["player_id"] == "p2"
    assert pert.observation["public"]["turn_order"] == ["p2", "p3", "p1"]
    assert pert.best_action_id == "b"
    assert pert.action_values == original.action_values
