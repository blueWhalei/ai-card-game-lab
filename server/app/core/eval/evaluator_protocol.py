"""Build ``EvaluatorParams`` from frozen protocol / settings snapshots."""

from __future__ import annotations

from typing import Any

from app.core.eval.rollout import EvaluatorParams
from app.core.task_protocol import protocol_evaluator


def evaluator_params_from_mapping(raw: dict[str, Any] | None) -> EvaluatorParams | None:
    """Lift a protocol ``scorer.evaluator`` dict into ``EvaluatorParams``.

    Per-move ``seed`` is never frozen here — callers keep scoring seeds local.
    """
    if not isinstance(raw, dict) or not raw:
        return None
    return EvaluatorParams(
        determinizations=int(raw.get("determinizations") or 4),
        rollouts_per_world=int(raw.get("rollouts_per_world") or 1),
        max_candidates=int(raw.get("max_candidates") or 8),
        max_steps=int(raw.get("max_steps") or 400),
        opponent_kind=str(raw.get("opponent_kind") or "heuristic"),
        seed=0,
    )


def protocol_evaluator_params(protocol: dict[str, Any] | None) -> EvaluatorParams | None:
    if not isinstance(protocol, dict):
        return None
    return evaluator_params_from_mapping(protocol_evaluator(protocol))


def freeze_evaluator_snapshot(
    *,
    determinizations: int,
    max_candidates: int,
    rollouts_per_world: int = 1,
    max_steps: int = 400,
    opponent_kind: str = "heuristic",
) -> dict[str, Any]:
    """Settings → protocol ``scorer.evaluator`` (no seed)."""
    return EvaluatorParams(
        determinizations=determinizations,
        rollouts_per_world=rollouts_per_world,
        max_candidates=max_candidates,
        max_steps=max_steps,
        opponent_kind=opponent_kind,
        seed=0,
    ).to_dict()
