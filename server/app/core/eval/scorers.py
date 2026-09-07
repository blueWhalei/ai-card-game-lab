"""Built-in scorers (game-agnostic) and registry assembly by game type."""

from __future__ import annotations

from app.core.eval.scorer import MetricResult, ScoreBundle, ScorerRegistry

# Engine-specific scorers are registered only for their game_type so a second
# engine does not inherit Dou Dizhu role metrics by accident.
_ENGINE_SCORER_LOADERS: dict[str, tuple[str, str]] = {
    "doudizhu": ("app.core.engine.doudizhu.scorers", "LandlordRoleScorer"),
}


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


class LatencyPercentileScorer:
    """Round latency P50 as the primary value; P95 in extras."""

    metric_id = "latency_p50_p95"

    def score(self, bundle: ScoreBundle) -> MetricResult:
        return MetricResult(
            metric_id=self.metric_id,
            value=round(bundle.p50_response_ms, 1),
            n=0,
            extras={"p95_response_ms": round(bundle.p95_response_ms, 1)},
        )


class EvLossScorer:
    """Mean EV loss over evaluated decision points (NULL losses excluded)."""

    metric_id = "ev_loss"

    def score(self, bundle: ScoreBundle) -> MetricResult:
        n = bundle.evaluated_count
        avg = bundle.avg_ev_loss
        value = 0.0 if avg is None or n == 0 else float(avg)
        return MetricResult(
            metric_id=self.metric_id,
            value=round(value, 4),
            n=n,
            extras={"avg_ev_loss": None if n == 0 else round(value, 4)},
        )


def _register_common(registry: ScorerRegistry) -> None:
    registry.register(TrainUsableScorer())
    registry.register(ParserSuccessScorer())
    registry.register(LatencyPercentileScorer())
    registry.register(EvLossScorer())


def _register_engine_scorers(registry: ScorerRegistry, game_type: str) -> None:
    import importlib

    spec = _ENGINE_SCORER_LOADERS.get(game_type)
    if spec is None:
        return
    module_name, class_name = spec
    module = importlib.import_module(module_name)
    scorer_cls = getattr(module, class_name)
    registry.register(scorer_cls())


def build_scorer_registry(*, game_type: str | None = None) -> ScorerRegistry:
    """Assemble scorers for one game type.

    Common metrics always register. Engine-specific metrics (e.g.
    ``role:landlord``) register only when ``game_type`` matches.
    """
    registry = ScorerRegistry()
    _register_common(registry)
    if game_type:
        _register_engine_scorers(registry, game_type)
    return registry


def build_default_scorer_registry() -> ScorerRegistry:
    """Product default: Dou Dizhu common + engine scorers."""
    return build_scorer_registry(game_type="doudizhu")
