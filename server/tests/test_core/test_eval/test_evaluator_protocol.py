"""Protocol-frozen EvaluatorParams helpers."""

from __future__ import annotations

from app.core.eval.evaluator_protocol import (
    freeze_evaluator_snapshot,
    protocol_evaluator_params,
)
from app.core.eval.rollout import EvaluatorParams
from app.core.task_protocol import build_protocol, protocol_evaluator


def test_freeze_evaluator_snapshot_omits_nothing_essential() -> None:
    snap = freeze_evaluator_snapshot(determinizations=6, max_candidates=12)
    assert snap["determinizations"] == 6
    assert snap["max_candidates"] == 12
    assert snap["opponent_kind"] == "heuristic"
    assert "seed" in snap


def test_protocol_evaluator_params_round_trip() -> None:
    protocol = build_protocol(
        players=[{"id": "a"}],
        source_experiment_id=None,
        pair_deals=False,
        deal_seeds=[],
        frozen_at="t0",
        prompt_version="v3",
        collect_mode="free",
        protocol_fingerprint={"game_type": "doudizhu", "eval_metric_ids": []},
        evaluator=freeze_evaluator_snapshot(determinizations=3, max_candidates=5),
    )
    assert protocol_evaluator(protocol) is not None
    params = protocol_evaluator_params(protocol)
    assert isinstance(params, EvaluatorParams)
    assert params.determinizations == 3
    assert params.max_candidates == 5


def test_missing_evaluator_returns_none() -> None:
    protocol = build_protocol(
        players=[{"id": "a"}],
        source_experiment_id=None,
        pair_deals=False,
        deal_seeds=[],
        frozen_at="t0",
        prompt_version="v3",
        collect_mode="free",
        protocol_fingerprint={"game_type": "doudizhu"},
    )
    assert protocol_evaluator(protocol) is None
    assert protocol_evaluator_params(protocol) is None
