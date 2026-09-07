"""Pydantic models for data management endpoints."""


from pydantic import BaseModel, Field


class CreateDatasetFromDecisionsRequest(BaseModel):
    """Register a ChatML dataset from decision_points (train_usable preferred)."""

    name: str
    game_type: str = "doudizhu"
    game_id: str | None = None
    experiment_id: str | None = None
    player_id: str | None = None
    min_quality: float | None = None
    outcome: str | None = None
    game_phase: str | None = None
    train_usable: bool | None = None
    train_usable_only: bool = True
    # Structural validity (train_usable) and move quality (ev_loss) are separate
    # questions, so they stay separate filters. Unevaluated moves are kept.
    max_ev_loss: float | None = None
    include_thinking: bool = False
    eval_ratio: float = Field(default=0.0, ge=0.0, le=0.5)
