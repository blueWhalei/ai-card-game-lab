"""Pydantic models for data management endpoints."""

from datetime import datetime

from pydantic import BaseModel


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
