"""Pydantic models for experiment config management endpoints."""

from pydantic import BaseModel


class ModelConfig(BaseModel):
    provider: str
    model_name: str
    temperature: float = 0.8
    top_p: float = 0.95
    max_tokens: int = 1024


class CreateExperimentConfigRequest(BaseModel):
    id: str
    name: str
    notes: str = ""
    model_config_data: ModelConfig


class UpdateExperimentConfigRequest(BaseModel):
    name: str | None = None
    notes: str | None = None
    model_config_data: ModelConfig | None = None
