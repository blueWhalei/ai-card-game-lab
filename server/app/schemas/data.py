"""Pydantic models for data management endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class DatasetFilters(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    player_ids: list[str] | None = None
    result: str | None = None
    min_quality_score: float | None = None
    include_chain_of_thought: bool = True


class CreateDatasetRequest(BaseModel):
    name: str
    game_type: str
    filters: DatasetFilters


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
    include_thinking: bool = False
    eval_ratio: float = Field(default=0.0, ge=0.0, le=0.5)
