"""Pydantic models for experiment config management endpoints."""

from pydantic import BaseModel, Field, field_validator


class ModelConfig(BaseModel):
    provider: str
    model_name: str
    temperature: float = 0.8
    top_p: float = 0.95
    max_tokens: int = 1024


class CreateExperimentConfigRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    notes: str = ""
    model_config_data: ModelConfig

    @field_validator("id", "name")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class UpdateExperimentConfigRequest(BaseModel):
    name: str | None = None
    notes: str | None = None
    model_config_data: ModelConfig | None = None
