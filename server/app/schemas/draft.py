"""Current workspace draft contract; partial text is valid before publication."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.experiment import (
    ResearchEvidenceRequest,
    ResearchPuzzleRequest,
    ResearchTraceRequest,
)

DraftKind = Literal["experiment", "comparison"]


class NotebookDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["experiment"]
    hypothesis: str = Field(max_length=10000)
    notes: str = Field(max_length=10000)
    conclusion: str = Field(max_length=10000)
    tags_input: str = Field(max_length=2000)


class ComparisonDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["comparison"]
    expected_revision: int = Field(ge=0)
    observations: str = Field(max_length=10000)
    interpretation: str = Field(max_length=10000)
    limitations: str = Field(max_length=10000)
    evidence: list[ResearchEvidenceRequest] = Field(max_length=30)
    puzzle_evidence: list[ResearchPuzzleRequest] = Field(default_factory=list, max_length=5)
    trace_evidence: list[ResearchTraceRequest] = Field(default_factory=list, max_length=5)


DraftContent = Annotated[NotebookDraft | ComparisonDraft, Field(discriminator="kind")]


class DraftRecord(BaseModel):
    revision: int
    updated_at: str | None
    content: DraftContent


class SaveDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    content: DraftContent
