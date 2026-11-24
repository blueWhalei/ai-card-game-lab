"""Strict input contracts for research organization."""

from pydantic import BaseModel, ConfigDict, Field


class CreateStudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    question: str = Field(default="", max_length=2000)


class AttachStudyRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str = Field(min_length=1, max_length=128)
