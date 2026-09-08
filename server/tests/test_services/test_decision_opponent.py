"""DecisionEvaluator opponent_kind resolution."""

from __future__ import annotations

from app.core.eval.rollout import EvaluatorParams
from app.core.policy.baselines import HeuristicPolicy, RandomPolicy
from app.services.decision_eval import DecisionEvaluator, resolve_opponent


def test_resolve_opponent_random() -> None:
    policy = resolve_opponent("random")
    assert isinstance(policy, RandomPolicy)
    assert policy.kind == "random"


def test_resolve_opponent_unknown_falls_back() -> None:
    policy = resolve_opponent("not-a-real-kind")
    assert isinstance(policy, HeuristicPolicy)


def test_decision_evaluator_uses_opponent_kind() -> None:
    evaluator = DecisionEvaluator(EvaluatorParams(opponent_kind="random"))
    assert isinstance(evaluator._opponent, RandomPolicy)
