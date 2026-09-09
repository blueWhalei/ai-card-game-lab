"""DecisionEvaluator opponent_kind resolution (including self-play)."""

from __future__ import annotations

from app.core.eval.rollout import EvaluatorParams
from app.core.policy.baselines import FirstActionPolicy, HeuristicPolicy, RandomPolicy
from app.services.decision_eval import (
    SELF_OPPONENT_KIND,
    DecisionEvaluator,
    resolve_opponent,
    resolve_opponent_for_score,
)


def test_resolve_opponent_random() -> None:
    policy = resolve_opponent("random")
    assert isinstance(policy, RandomPolicy)
    assert policy.kind == "random"


def test_resolve_opponent_unknown_falls_back() -> None:
    policy = resolve_opponent("not-a-real-kind")
    assert isinstance(policy, HeuristicPolicy)


def test_resolve_opponent_self_without_selector_falls_back() -> None:
    policy = resolve_opponent(SELF_OPPONENT_KIND)
    assert isinstance(policy, HeuristicPolicy)


def test_decision_evaluator_uses_opponent_kind() -> None:
    evaluator = DecisionEvaluator(EvaluatorParams(opponent_kind="random"))
    assert isinstance(evaluator._opponent, RandomPolicy)


def test_self_with_baseline_selector_is_true_self_play() -> None:
    seat = FirstActionPolicy()
    params = EvaluatorParams(opponent_kind=SELF_OPPONENT_KIND, self_proxy="heuristic")
    opponent, honesty = resolve_opponent_for_score(params, seat)
    assert opponent is seat
    assert honesty["opponent_kind_requested"] == SELF_OPPONENT_KIND
    assert honesty["opponent_kind_effective"] == "first"


def test_self_without_baseline_uses_proxy_honestly() -> None:
    params = EvaluatorParams(opponent_kind=SELF_OPPONENT_KIND, self_proxy="random")
    opponent, honesty = resolve_opponent_for_score(params, None)
    assert isinstance(opponent, RandomPolicy)
    assert honesty["opponent_kind_requested"] == SELF_OPPONENT_KIND
    assert honesty["opponent_kind_effective"] == "random"


def test_freeze_includes_self_proxy() -> None:
    from app.core.eval.evaluator_protocol import freeze_evaluator_snapshot

    snap = freeze_evaluator_snapshot(
        determinizations=2,
        max_candidates=4,
        opponent_kind="self",
        self_proxy="first",
    )
    assert snap["opponent_kind"] == "self"
    assert snap["self_proxy"] == "first"
