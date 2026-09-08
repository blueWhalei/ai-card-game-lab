"""Unit tests for experiment-level Scorers."""

from __future__ import annotations

from app.core.engine.doudizhu.scorers import LandlordRoleScorer
from app.core.eval.scorer import (
    ScoreBundle,
    ScorerRegistry,
    apply_scorer_results,
    score_bundle_from_aggregates,
)
from app.core.eval.scorers import (
    EvLossScorer,
    LatencyPercentileScorer,
    ParserSuccessScorer,
    TrainUsableScorer,
    build_default_scorer_registry,
    build_scorer_registry,
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
        ["train_usable", "not_a_real_metric", "parser_success"],
        ScoreBundle(decision_count=2, train_usable_n=1, parser_n=2, parser_ok=2),
    )
    assert set(results) == {"train_usable", "parser_success"}
    assert "not_a_real_metric" not in results


def test_apply_scorer_results_overlays_summary_keys() -> None:
    aggregates = {
        "decision_count": 10,
        "train_usable_n": 4,
        "train_usable_rate": 0.0,
        "parser_n": 8,
        "parser_ok": 6,
        "parser_success_rate": 0.0,
        "landlord_win_rate": 0.0,
        "decisive_games": 20,
        "wins_by_role": {"landlord": 11, "peasant": 9},
        "p50_response_ms": 100.0,
        "p95_response_ms": 200.0,
        "evaluated_count": 5,
        "avg_ev_loss": 0.25,
    }
    registry = ScorerRegistry()
    registry.register(TrainUsableScorer())
    registry.register(ParserSuccessScorer())
    registry.register(LatencyPercentileScorer())
    registry.register(LandlordRoleScorer())
    registry.register(EvLossScorer())
    scored = registry.score_many(
        [
            "train_usable",
            "parser_success",
            "role:landlord",
            "latency_p50_p95",
            "ev_loss",
        ],
        score_bundle_from_aggregates(aggregates),
    )
    merged = apply_scorer_results(aggregates, scored)
    assert merged["train_usable_rate"] == 0.4
    assert merged["parser_success_rate"] == 0.75
    assert merged["landlord_win_rate"] == 0.55
    assert merged["p50_response_ms"] == 100.0
    assert merged["p95_response_ms"] == 200.0
    assert merged["avg_ev_loss"] == 0.25
    assert merged["evaluated_count"] == 5


def test_empty_bundle_rates_are_zero() -> None:
    empty = ScoreBundle()
    assert TrainUsableScorer().score(empty).value == 0.0
    assert ParserSuccessScorer().score(empty).value == 0.0
    assert EvLossScorer().score(empty).n == 0
    assert EvLossScorer().score(empty).extras["avg_ev_loss"] is None


def test_landlord_and_latency_scorers() -> None:
    bundle = ScoreBundle(
        decisive_games=10,
        wins_by_role={"landlord": 4, "peasant": 6},
        p50_response_ms=12.34,
        p95_response_ms=56.78,
    )
    landlord = LandlordRoleScorer().score(bundle)
    assert landlord.value == 0.4
    assert landlord.n == 10
    assert landlord.extras["landlord_role_wins"] == 4
    latency = LatencyPercentileScorer().score(bundle)
    assert latency.value == 12.3
    assert latency.extras["p95_response_ms"] == 56.8


def test_registry_by_game_type() -> None:
    bare = build_scorer_registry(game_type=None)
    assert "role:landlord" not in bare.list_ids()
    assert "ev_loss" in bare.list_ids()

    doudizhu = build_scorer_registry(game_type="doudizhu")
    assert "role:landlord" in doudizhu.list_ids()

    other = build_scorer_registry(game_type="holdem")
    assert "role:landlord" not in other.list_ids()


def test_default_registry_covers_doudizhu_eval_metric_ids() -> None:
    ids = set(build_default_scorer_registry().list_ids())
    assert {
        "train_usable",
        "parser_success",
        "latency_p50_p95",
        "role:landlord",
        "ev_loss",
    } <= ids
