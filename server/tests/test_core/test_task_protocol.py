"""Unit tests for Task protocol (dataset × solver × scorer)."""

from __future__ import annotations

import pytest

from app.core.task_protocol import (
    PROTOCOL_SCHEMA_VERSION,
    build_protocol,
    flatten_protocol_view,
    protocol_deal_seeds,
    protocol_players,
    set_protocol_deal_seeds,
    validate_protocol,
)


def test_build_protocol_nests_sections() -> None:
    protocol = build_protocol(
        players=[{"id": "a"}],
        source_experiment_id=None,
        pair_deals=False,
        deal_seeds=[1, 2],
        frozen_at="t0",
        prompt_version="v3",
        collect_mode="benchmark",
        protocol_fingerprint={
            "game_type": "doudizhu",
            "engine_version": "1",
            "decision_schema_version": 2,
            "rules_ref": None,
            "phases": ["bidding"],
            "prompt_keys": {"playing": "p"},
            "roles": ["landlord"],
            "eval_metric_ids": ["parser_success"],
            "supports_deal_seed": True,
            "benchmark_seed_count": 50,
        },
        evaluator={
            "determinizations": 4,
            "rollouts_per_world": 1,
            "max_candidates": 8,
            "max_steps": 400,
            "opponent_kind": "heuristic",
            "seed": 0,
        },
    )
    assert protocol["schema_version"] == PROTOCOL_SCHEMA_VERSION
    assert protocol["scorer"]["evaluator"]["determinizations"] == 4
    assert protocol["dataset"]["deal_seeds"] == [1, 2]
    assert protocol["solver"]["players"][0]["id"] == "a"
    assert protocol["scorer"]["eval_metric_ids"] == ["parser_success"]
    assert protocol["engine"]["game_type"] == "doudizhu"
    assert "players" not in protocol
    assert "deal_seeds" not in protocol


def test_validate_rejects_v1_and_missing_sections() -> None:
    with pytest.raises(ValueError, match="不受支持"):
        validate_protocol({"schema_version": 1, "players": [{"id": "a"}]})
    with pytest.raises(ValueError, match="dataset"):
        validate_protocol(
            {
                "schema_version": 2,
                "solver": {"players": [{"id": "a"}], "prompt_version": "v3"},
                "scorer": {"eval_metric_ids": []},
                "engine": {},
            }
        )


def test_set_deal_seeds_and_flatten() -> None:
    protocol = build_protocol(
        players=[{"id": "a"}],
        source_experiment_id="src",
        pair_deals=True,
        deal_seeds=[],
        frozen_at="t0",
        prompt_version="v3",
        collect_mode="free",
        protocol_fingerprint={"game_type": "doudizhu", "engine_version": "1"},
    )
    set_protocol_deal_seeds(protocol, [9, 8])
    assert protocol_deal_seeds(protocol) == [9, 8]
    flat = flatten_protocol_view(protocol)
    assert flat is not None
    assert flat["deal_seeds"] == [9, 8]
    assert flat["pair_deals"] is True
    assert flat["source_experiment_id"] == "src"
    assert protocol_players(protocol) == [{"id": "a"}]
