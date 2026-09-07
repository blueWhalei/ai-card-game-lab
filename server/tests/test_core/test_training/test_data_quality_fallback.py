"""train_usable heuristics for rescue / parse-fallback paths."""

from app.core.training.data_quality import evaluate_train_usable

_PROMPT = [{"role": "user", "content": "pick an action"}]


def test_parse_fallback_not_train_usable() -> None:
    usable, reason = evaluate_train_usable(
        action_id="PASS||",
        legal_action_ids=["PASS||"],
        prompt_messages=_PROMPT,
        parse_fallback=True,
    )
    assert usable is False
    assert reason == "rescue_action"


def test_structural_ok_without_fallback() -> None:
    usable, reason = evaluate_train_usable(
        action_id="PASS||",
        legal_action_ids=["PASS||"],
        prompt_messages=_PROMPT,
        parse_fallback=False,
    )
    assert usable is True
    assert reason == "ok"
