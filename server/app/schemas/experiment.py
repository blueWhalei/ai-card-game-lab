"""Pydantic models for experiment (run) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str = ""
    game_type: str = "doudizhu"
    player_ids: list[str] = Field(min_length=2, max_length=16)
    target_games: int = Field(default=10, ge=1, le=50)
    source_experiment_id: str | None = None
    pair_deals: bool = False


class CollectExperimentRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=50)
