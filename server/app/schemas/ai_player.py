"""Pydantic models for AI player management endpoints."""

from pydantic import BaseModel


class ModelConfig(BaseModel):
    provider: str
    model_name: str
    temperature: float = 0.8
    top_p: float = 0.95
    max_tokens: int = 1024


class CreateAIPlayerRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    avatar: str = ""
    model_config_data: ModelConfig


class UpdateAIPlayerRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    avatar: str | None = None
    model_config_data: ModelConfig | None = None
