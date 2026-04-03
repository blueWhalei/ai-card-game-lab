"""Request and response schemas for prompt template management."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PromptTemplateResponse(BaseModel):
    """Response model for a prompt template."""

    id: str
    template_key: str = Field(description="Template identifier, e.g., 'doudizhu_playing'")
    version: str = Field(description="Template version, e.g., 'v1', 'v2'")
    content: str = Field(description="Template content with placeholders")
    is_active: bool = Field(description="Whether this template version is active")
    created_at: str = Field(description="ISO timestamp of creation")
    updated_at: str = Field(description="ISO timestamp of last update")


class CreatePromptRequest(BaseModel):
    """Request model for creating a new prompt template."""

    template_key: str = Field(
        ..., description="Template identifier, e.g., 'doudizhu_playing'", min_length=1
    )
    version: str = Field(..., description="Template version, e.g., 'v1', 'v2'", min_length=1)
    content: str = Field(..., description="Template content with placeholders", min_length=1)


class UpdatePromptRequest(BaseModel):
    """Request model for updating an existing prompt template."""

    content: str = Field(..., description="Updated template content", min_length=1)


class ABTestConfig(BaseModel):
    """A/B test configuration for prompt templates."""

    enabled: bool = Field(description="Whether A/B testing is enabled")
    ratio: float = Field(
        description="Ratio of requests assigned to treatment group (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )


class ABStatsResponse(BaseModel):
    """Response model for A/B test statistics."""

    enabled: bool = Field(description="Whether A/B testing is enabled")
    ratio: float = Field(description="A/B test ratio")
    total_assignments: int = Field(description="Total number of session assignments")
    v1_count: int = Field(description="Number of sessions assigned to v1")
    v2_count: int = Field(description="Number of sessions assigned to v2")


class ActivatePromptRequest(BaseModel):
    """Request model for activating a prompt template."""

    version: str = Field(..., description="Version to activate")


class DeactivatePromptRequest(BaseModel):
    """Request model for deactivating a prompt template."""

    version: str = Field(..., description="Version to deactivate")
