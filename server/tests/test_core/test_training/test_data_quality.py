"""Unit tests for train_usable heuristics."""

from __future__ import annotations

from app.core.training.data_quality import evaluate_train_usable

_PROMPT = [{"role": "user", "content": "pick an action"}]


class TestEvaluateTrainUsable:
    def test_valid_action_id(self) -> None:
        usable, reason = evaluate_train_usable(
            action_id="SINGLE|C3|",
            legal_action_ids=["SINGLE|C3|", "PASS||"],
            prompt_messages=_PROMPT,
        )
        assert usable is True
        assert reason == "ok"

    def test_action_id_not_legal(self) -> None:
        usable, reason = evaluate_train_usable(
            action_id="BOMB|C3 D3 H3 S3|",
            legal_action_ids=["PASS||"],
            prompt_messages=_PROMPT,
        )
        assert usable is False
        assert reason == "action_id_not_legal"

    def test_no_action_id(self) -> None:
        usable, reason = evaluate_train_usable(
            action_id="",
            legal_action_ids=["PASS||"],
            prompt_messages=_PROMPT,
        )
        assert usable is False
        assert reason == "no_action_id"

    def test_no_prompt_recorded(self) -> None:
        usable, reason = evaluate_train_usable(
            action_id="PASS||",
            legal_action_ids=["PASS||"],
            prompt_messages=None,
        )
        assert usable is False
        assert reason == "no_prompt_recorded"

    def test_no_legal_actions(self) -> None:
        usable, reason = evaluate_train_usable(
            action_id="PASS||",
            legal_action_ids=[],
            prompt_messages=_PROMPT,
        )
        assert usable is False
        assert reason == "no_legal_actions"

    def test_parse_fallback_not_usable(self) -> None:
        usable, reason = evaluate_train_usable(
            action_id="PASS||",
            legal_action_ids=["PASS||"],
            prompt_messages=_PROMPT,
            parse_fallback=True,
        )
        assert usable is False
        assert reason == "rescue_action"
