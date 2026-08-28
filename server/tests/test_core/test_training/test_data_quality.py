"""Unit tests for train_usable heuristics."""

from __future__ import annotations

import pytest

from app.core.training.data_quality import evaluate_train_usable


class TestEvaluateTrainUsable:
    def test_valid_play_action(self) -> None:
        chosen = {"action_type": "SINGLE", "cards": ["C3"]}
        legal = [
            {"action_type": "SINGLE", "cards": ["C3"]},
            {"action_type": "PASS", "cards": []},
        ]
        usable, reason = evaluate_train_usable(
            chosen_action=chosen,
            legal_actions=legal,
            thinking="出最小单张",
        )
        assert usable is True
        assert reason == "ok"

    def test_chosen_not_in_legal(self) -> None:
        chosen = {"action_type": "BOMB", "cards": ["C3", "D3", "H3", "S3"]}
        legal = [{"action_type": "PASS", "cards": []}]
        usable, reason = evaluate_train_usable(
            chosen_action=chosen,
            legal_actions=legal,
            thinking=None,
        )
        assert usable is False
        assert reason == "chosen_not_in_legal_actions"

    def test_empty_chosen(self) -> None:
        usable, reason = evaluate_train_usable(
            chosen_action={},
            legal_actions=[{"action_type": "PASS", "cards": []}],
            thinking=None,
        )
        assert usable is False
        assert reason in {"empty_chosen_action", "missing_action_type"}

    def test_card_order_normalized(self) -> None:
        chosen = {"action_type": "PAIR", "cards": ["D4", "C4"]}
        legal = [{"action_type": "PAIR", "cards": ["C4", "D4"]}]
        usable, reason = evaluate_train_usable(
            chosen_action=chosen,
            legal_actions=legal,
            thinking=None,
        )
        assert usable is True
        assert reason == "ok"

    def test_thinking_pass_action_play(self) -> None:
        chosen = {"action_type": "SINGLE", "cards": ["C3"]}
        legal = [
            {"action_type": "SINGLE", "cards": ["C3"]},
            {"action_type": "PASS", "cards": []},
        ]
        usable, reason = evaluate_train_usable(
            chosen_action=chosen,
            legal_actions=legal,
            thinking="选择PASS，保存实力",
        )
        assert usable is False
        assert reason == "thinking_pass_action_play"

    def test_thinking_play_action_pass(self) -> None:
        chosen = {"action_type": "PASS", "cards": []}
        legal = [
            {"action_type": "SINGLE", "cards": ["C3"]},
            {"action_type": "PASS", "cards": []},
        ]
        usable, reason = evaluate_train_usable(
            chosen_action=chosen,
            legal_actions=legal,
            thinking="决定出单张管上",
        )
        assert usable is False
        assert reason == "thinking_play_action_pass"

    def test_no_thinking_is_usable(self) -> None:
        chosen = {"action_type": "PASS", "cards": []}
        legal = [{"action_type": "PASS", "cards": []}]
        usable, reason = evaluate_train_usable(
            chosen_action=chosen,
            legal_actions=legal,
            thinking=None,
        )
        assert usable is True
        assert reason == "ok"

    def test_type_alias_key(self) -> None:
        chosen = {"type": "PASS", "cards": []}
        legal = [{"type": "PASS", "cards": []}]
        usable, _ = evaluate_train_usable(
            chosen_action=chosen,
            legal_actions=legal,
            thinking="",
        )
        assert usable is True
