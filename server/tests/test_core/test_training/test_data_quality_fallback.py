"""train_usable heuristics for LLM fallback paths."""

from app.core.training.data_quality import evaluate_train_usable


def test_llm_call_fallback_not_train_usable() -> None:
    usable, reason = evaluate_train_usable(
        chosen_action={"type": "PASS", "cards": []},
        legal_actions=[{"type": "PASS", "cards": []}],
        thinking="[LLM调用失败，使用默认动作] timeout",
    )
    assert usable is False
    assert reason == "llm_fallback_action"


def test_llm_parse_fallback_not_train_usable() -> None:
    usable, reason = evaluate_train_usable(
        chosen_action={"type": "PASS", "cards": []},
        legal_actions=[{"type": "PASS", "cards": []}],
        thinking="[LLM解析失败，使用默认动作] garbage",
    )
    assert usable is False
    assert reason == "llm_fallback_action"
