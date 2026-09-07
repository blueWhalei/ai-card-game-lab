"""Evaluation package: what a decision was worth, and experiment-level scorers."""

from app.core.eval.puzzle import (
    PUZZLE_PACK_KIND,
    PUZZLE_SCHEMA_VERSION,
    Puzzle,
    PuzzleAnswerScore,
    PuzzlePackManifest,
    load_pack,
    save_pack,
    score_answer,
    select_by_spread,
)
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
    "PUZZLE_PACK_KIND",
    "PUZZLE_SCHEMA_VERSION",
    "EvLoss",
    "EvaluatorParams",
    "MetricResult",
    "Puzzle",
    "PuzzleAnswerScore",
    "PuzzlePackManifest",
    "RolloutEvaluator",
    "ScoreBundle",
    "ScorerRegistry",
    "apply_scorer_results",
    "build_default_scorer_registry",
    "build_scorer_registry",
    "load_pack",
    "save_pack",
    "score_answer",
    "score_bundle_from_aggregates",
    "select_by_spread",
]
