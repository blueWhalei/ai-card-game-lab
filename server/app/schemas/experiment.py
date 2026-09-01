"""Pydantic models for experiment (run) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str = ""
    hypothesis: str = ""
    tags: list[str] = Field(default_factory=list, max_length=20)
    game_type: str = "doudizhu"
    player_ids: list[str] = Field(min_length=2, max_length=16)
    target_games: int = Field(default=10, ge=1, le=50)
    source_experiment_id: str | None = None
    pair_deals: bool = False
    collect_mode: str = Field(default="free", pattern="^(free|benchmark)$")


class UpdateExperimentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = None
    hypothesis: str | None = None
    conclusion: str | None = None
    tags: list[str] | None = Field(default=None, max_length=20)


class CloneExperimentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    copy_deal_seeds: bool = True
    copy_hypothesis: bool = True


class CollectExperimentRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=50)
