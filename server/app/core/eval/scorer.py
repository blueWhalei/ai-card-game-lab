"""Scorer: turn persisted game/decision counts into named metrics.

Scorers never open a database or run a game. They read a ``ScoreBundle`` that
the service layer filled from already-stored rows (see ROADMAP §9.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class MetricResult:
    """One scored metric for an experiment summary."""

    metric_id: str
    value: float
    n: int = 0
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "metric_id": self.metric_id,
            "value": self.value,
            "n": self.n,
        }
        payload.update(self.extras)
        return payload


@dataclass(frozen=True)
class ScoreBundle:
    """Read-only counts scorers may consume.

    Filled from ``eval_aggregates`` today; later sources can swap in without
    changing Scorer implementations.
    """

    decision_count: int = 0
    train_usable_n: int = 0
    parser_n: int = 0
    parser_ok: int = 0
    decisive_games: int = 0
    wins_by_role: dict[str, int] = field(default_factory=dict)
    p50_response_ms: float = 0.0
    p95_response_ms: float = 0.0
    evaluated_count: int = 0
    avg_ev_loss: float | None = None


class Scorer(Protocol):
    """Pure metric over a ``ScoreBundle``."""

    metric_id: str

    def score(self, bundle: ScoreBundle) -> MetricResult: ...


class ScorerRegistry:
    """Maps ``eval_metric_ids`` entries to scorer implementations."""

    def __init__(self) -> None:
        self._scorers: dict[str, Scorer] = {}

    def register(self, scorer: Scorer) -> None:
        self._scorers[scorer.metric_id] = scorer

    def get(self, metric_id: str) -> Scorer | None:
        return self._scorers.get(metric_id)

    def list_ids(self) -> list[str]:
        return list(self._scorers)

    def score_many(
        self,
        metric_ids: list[str],
        bundle: ScoreBundle,
    ) -> dict[str, MetricResult]:
        """Score registered ids only; unknown ids are skipped."""
        results: dict[str, MetricResult] = {}
        for metric_id in metric_ids:
            scorer = self._scorers.get(metric_id)
            if scorer is None:
                continue
            results[metric_id] = scorer.score(bundle)
        return results


def score_bundle_from_aggregates(eval_metrics: dict[str, Any]) -> ScoreBundle:
    """Lift raw aggregate counts into a bundle for scorers."""
    raw_roles = eval_metrics.get("wins_by_role") or {}
    wins_by_role: dict[str, int] = {}
    if isinstance(raw_roles, dict):
        wins_by_role = {str(k): int(v or 0) for k, v in raw_roles.items()}
    avg_raw = eval_metrics.get("avg_ev_loss")
    avg_ev_loss = float(avg_raw) if avg_raw is not None else None
    return ScoreBundle(
        decision_count=int(eval_metrics.get("decision_count") or 0),
        train_usable_n=int(eval_metrics.get("train_usable_n") or 0),
        parser_n=int(eval_metrics.get("parser_n") or 0),
        parser_ok=int(eval_metrics.get("parser_ok") or 0),
        decisive_games=int(eval_metrics.get("decisive_games") or 0),
        wins_by_role=wins_by_role,
        p50_response_ms=float(eval_metrics.get("p50_response_ms") or 0.0),
        p95_response_ms=float(eval_metrics.get("p95_response_ms") or 0.0),
        evaluated_count=int(eval_metrics.get("evaluated_count") or 0),
        avg_ev_loss=avg_ev_loss,
    )


def apply_scorer_results(
    eval_metrics: dict[str, Any],
    results: dict[str, MetricResult],
) -> dict[str, Any]:
    """Overlay scorer outputs onto aggregate fields (stable summary keys)."""
    out = dict(eval_metrics)
    train = results.get("train_usable")
    if train is not None:
        out["train_usable_rate"] = train.value
        out["decision_count"] = train.n
        out["train_usable_n"] = int(train.extras.get("train_usable_n", train.n))
    parser = results.get("parser_success")
    if parser is not None:
        out["parser_success_rate"] = parser.value
        out["parser_n"] = parser.n
        if "parser_ok" in parser.extras:
            out["parser_ok"] = int(parser.extras["parser_ok"])
    landlord = results.get("role:landlord")
    if landlord is not None:
        out["landlord_win_rate"] = landlord.value
        out["decisive_games"] = landlord.n
        wins_by_role = dict(out.get("wins_by_role") or {})
        wins_by_role["landlord"] = int(
            landlord.extras.get("landlord_role_wins", wins_by_role.get("landlord", 0))
        )
        out["wins_by_role"] = wins_by_role
    latency = results.get("latency_p50_p95")
    if latency is not None:
        out["p50_response_ms"] = latency.value
        if "p95_response_ms" in latency.extras:
            out["p95_response_ms"] = float(latency.extras["p95_response_ms"])
    ev_loss = results.get("ev_loss")
    if ev_loss is not None:
        out["evaluated_count"] = ev_loss.n
        out["avg_ev_loss"] = (
            None if ev_loss.n == 0 else float(ev_loss.extras.get("avg_ev_loss", ev_loss.value))
        )
    return out
