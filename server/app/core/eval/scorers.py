"""Built-in scorers (game-agnostic rates over decision / trace counts)."""

from __future__ import annotations

from app.core.eval.scorer import MetricResult, ScoreBundle, ScorerRegistry


class TrainUsableScorer:
    """Fraction of decision points marked structurally train-usable."""

    metric_id = "train_usable"

    def score(self, bundle: ScoreBundle) -> MetricResult:
        n = bundle.decision_count
        usable = bundle.train_usable_n
        rate = (usable / n) if n else 0.0
        return MetricResult(
            metric_id=self.metric_id,
            value=round(rate, 4),
            n=n,
            extras={"train_usable_n": usable},
        )


class ParserSuccessScorer:
    """Fraction of traces whose metrics mark ``parser_ok``."""

    metric_id = "parser_success"

    def score(self, bundle: ScoreBundle) -> MetricResult:
        n = bundle.parser_n
        ok = bundle.parser_ok
        rate = (ok / n) if n else 0.0
        return MetricResult(
            metric_id=self.metric_id,
            value=round(rate, 4),
            n=n,
            extras={"parser_ok": ok},
        )


def build_default_scorer_registry() -> ScorerRegistry:
    """Registry with the first wave of common metrics."""
    registry = ScorerRegistry()
    registry.register(TrainUsableScorer())
    registry.register(ParserSuccessScorer())
    return registry
