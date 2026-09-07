"""Dou Dizhu–specific experiment scorers."""

from __future__ import annotations

from app.core.eval.scorer import MetricResult, ScoreBundle


class LandlordRoleScorer:
    """Landlord win rate among decisive (landlord/peasant) finished games."""

    metric_id = "role:landlord"

    def score(self, bundle: ScoreBundle) -> MetricResult:
        n = bundle.decisive_games
        wins = bundle.landlord_role_wins
        rate = (wins / n) if n else 0.0
        return MetricResult(
            metric_id=self.metric_id,
            value=round(rate, 4),
            n=n,
            extras={"landlord_role_wins": wins},
        )
