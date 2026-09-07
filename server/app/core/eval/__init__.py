"""Evaluation package: what a decision was worth, and experiment-level scorers."""

from app.core.eval.rollout import EvaluatorParams, EvLoss, RolloutEvaluator
from app.core.eval.scorer import (
    MetricResult,
    ScoreBundle,
    ScorerRegistry,
    apply_scorer_results,
    score_bundle_from_aggregates,
)
from app.core.eval.scorers import build_default_scorer_registry, build_scorer_registry

__all__ = [
    "EvLoss",
    "EvaluatorParams",
    "MetricResult",
    "RolloutEvaluator",
    "ScoreBundle",
    "ScorerRegistry",
    "apply_scorer_results",
    "build_default_scorer_registry",
    "build_scorer_registry",
    "score_bundle_from_aggregates",
]
