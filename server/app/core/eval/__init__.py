"""Evaluation package: what a decision was worth, and experiment-level scorers."""

from app.core.eval.perturb import (
    DEFAULT_PERTURB_KINDS,
    PerturbKind,
    ensure_perturb_kinds,
    perturb_puzzle,
)
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
    "DEFAULT_PERTURB_KINDS",
    "PUZZLE_PACK_KIND",
    "PUZZLE_SCHEMA_VERSION",
    "EvLoss",
    "EvaluatorParams",
    "MetricResult",
    "PerturbKind",
    "Puzzle",
    "PuzzleAnswerScore",
    "PuzzlePackManifest",
    "RolloutEvaluator",
    "ScoreBundle",
    "ScorerRegistry",
    "apply_scorer_results",
    "build_default_scorer_registry",
    "build_scorer_registry",
    "ensure_perturb_kinds",
    "load_pack",
    "perturb_puzzle",
    "save_pack",
    "score_answer",
    "score_bundle_from_aggregates",
    "select_by_spread",
]
