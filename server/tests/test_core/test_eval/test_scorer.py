"""Unit tests for experiment-level Scorers."""

from __future__ import annotations

from app.core.eval.scorer import (
    ScoreBundle,
    ScorerRegistry,
    apply_scorer_results,
    score_bundle_from_aggregates,
)
from app.core.eval.scorers import (
    ParserSuccessScorer,
    TrainUsableScorer,
    build_default_scorer_registry,
)


def test_train_usable_and_parser_rates() -> None:
    bundle = ScoreBundle(
        decision_count=10,
        train_usable_n=4,
        parser_n=8,
        parser_ok=6,
    )
    train = TrainUsableScorer().score(bundle)
    assert train.metric_id == "train_usable"
    assert train.value == 0.4
    assert train.n == 10
    assert train.extras["train_usable_n"] == 4

    parser = ParserSuccessScorer().score(bundle)
    assert parser.metric_id == "parser_success"
    assert parser.value == 0.75
    assert parser.n == 8
    assert parser.extras["parser_ok"] == 6


def test_score_many_skips_unregistered() -> None:
    registry = build_default_scorer_registry()
    results = registry.score_many(
        ["train_usable", "role:landlord", "parser_success"],
        ScoreBundle(decision_count=2, train_usable_n=1, parser_n=2, parser_ok=2),
    )
    assert set(results) == {"train_usable", "parser_success"}
    assert "role:landlord" not in results


def test_apply_scorer_results_overlays_summary_keys() -> None:
    aggregates = {
        "decision_count": 10,
        "train_usable_n": 4,
        "train_usable_rate": 0.0,
        "parser_n": 8,
        "parser_ok": 6,
        "parser_success_rate": 0.0,
        "landlord_win_rate": 0.55,
    }
    registry = ScorerRegistry()
    registry.register(TrainUsableScorer())
    registry.register(ParserSuccessScorer())
    scored = registry.score_many(
        ["train_usable", "parser_success"],
        score_bundle_from_aggregates(aggregates),
    )
    merged = apply_scorer_results(aggregates, scored)
    assert merged["train_usable_rate"] == 0.4
    assert merged["parser_success_rate"] == 0.75
    assert merged["landlord_win_rate"] == 0.55


def test_empty_bundle_rates_are_zero() -> None:
    empty = ScoreBundle()
    assert TrainUsableScorer().score(empty).value == 0.0
    assert ParserSuccessScorer().score(empty).value == 0.0
