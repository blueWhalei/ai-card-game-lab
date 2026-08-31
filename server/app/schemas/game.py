"""Pydantic models for game-related API endpoints."""

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    game_type: str
    player_ids: list[str]
    mode: str = "realtime"
    config: dict[str, object] | None = None
    experiment_id: str | None = None


class BatchCreateRequest(BaseModel):
    game_type: str
    player_ids: list[str]
    count: int = Field(ge=1, le=50, default=1)
    experiment_id: str | None = None

