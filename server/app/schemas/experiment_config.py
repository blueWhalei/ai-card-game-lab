"""Pydantic models for experiment config management endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PolicyKind = Literal["llm", "tool_loop", "search", "heuristic", "random", "first"]


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
    policy_kind: PolicyKind = "llm"
    model_config_data: ModelConfig | None = None

    @field_validator("id", "name")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @model_validator(mode="after")
    def require_model_for_llm(self) -> CreateExperimentConfigRequest:
        if self.policy_kind in ("llm", "tool_loop", "search") and self.model_config_data is None:
            raise ValueError("model_config_data is required when policy_kind uses an LLM")
        return self


class UpdateExperimentConfigRequest(BaseModel):
    name: str | None = None
    notes: str | None = None
    policy_kind: PolicyKind | None = None
    model_config_data: ModelConfig | None = None
