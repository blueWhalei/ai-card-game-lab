"""Coverage of a benchmark experiment's declared deal seeds."""

from __future__ import annotations

from app.core.stats.benchmark import build_benchmark_coverage


def _game(seed: int, status: str) -> dict[str, object]:
    return {"status": status, "metadata": {"deal_seed": seed}}


def test_free_collect_returns_none() -> None:
    assert (
        build_benchmark_coverage(
            protocol={"collect_mode": "free", "deal_seeds": [1, 2]},
            games=[_game(1, "finished")],
        )
        is None
    )


def test_missing_protocol_returns_none() -> None:
    assert build_benchmark_coverage(protocol=None, games=[]) is None


def test_complete_when_every_declared_seed_is_terminal() -> None:
    report = build_benchmark_coverage(
        protocol={"collect_mode": "benchmark", "deal_seeds": [10, 20, 30]},
        games=[_game(10, "finished"), _game(20, "finished"), _game(30, "no_bid")],
    )
    assert report is not None
    assert report["seed_total"] == 3
    assert report["seed_started"] == 3
    assert report["seed_finished"] == 3
    assert report["seed_failed"] == 0
    assert report["seed_running"] == 0
    assert report["seed_remaining"] == 0
    assert report["extra_games"] == 0
    assert report["complete"] is True


def test_running_and_remaining_keep_report_incomplete() -> None:
    report = build_benchmark_coverage(
        protocol={"collect_mode": "benchmark", "deal_seeds": [1, 2, 3, 4]},
        games=[_game(1, "finished"), _game(2, "running")],
    )
    assert report is not None
    assert report["seed_started"] == 2
    assert report["seed_finished"] == 1
    assert report["seed_running"] == 1
    assert report["seed_remaining"] == 2
    assert report["complete"] is False


def test_failed_seed_counts_as_coverage() -> None:
    report = build_benchmark_coverage(
        protocol={"collect_mode": "benchmark", "deal_seeds": [1, 2]},
        games=[_game(1, "failed"), _game(2, "cancelled")],
    )
    assert report is not None
    assert report["seed_finished"] == 2
    assert report["seed_failed"] == 2
    assert report["seed_remaining"] == 0
    assert report["complete"] is True


def test_extra_games_outside_declared_set() -> None:
    report = build_benchmark_coverage(
        protocol={"collect_mode": "benchmark", "deal_seeds": [1, 2]},
        games=[_game(1, "finished"), _game(99, "finished"), {"status": "finished"}],
    )
    assert report is not None
    assert report["seed_started"] == 1
    assert report["seed_remaining"] == 1
    assert report["extra_games"] == 2
    assert report["complete"] is False


def test_duplicate_seed_keeps_latest_and_does_not_double_count() -> None:
    report = build_benchmark_coverage(
        protocol={"collect_mode": "benchmark", "deal_seeds": [1]},
        games=[_game(1, "running"), _game(1, "failed")],
    )
    assert report is not None
    assert report["seed_started"] == 1
    assert report["seed_running"] == 0
    assert report["seed_failed"] == 1
    assert report["complete"] is True
