"""Pydantic models for experiment (run) endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateExperimentRequest(BaseModel):
    study_id: str | None = Field(default=None, min_length=1, max_length=128)
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
    prompt_version: str | None = Field(
        default=None,
        max_length=64,
        description="Template version to freeze into protocol.solver (default v3)",
    )


class OfflineExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    study_id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120, pattern=r"\S")
    hypothesis: str = Field(default="", max_length=10000)


class UpdateExperimentRequest(BaseModel):
    expected_draft_revision: int | None = Field(default=None, ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = None
    hypothesis: str | None = None
    conclusion: str | None = None
    tags: list[str] | None = Field(default=None, max_length=20)


class LandlordWinRate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["landlord_win_rate"]


class SeatTeamWinRate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["seat_team_win_rate"]
    player_id: str = Field(min_length=1, max_length=128)


class CreatePromptVariantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_revision_id: str | None = Field(default=None, min_length=1, max_length=128)
    study_id: str = Field(min_length=1, max_length=128)
    primary_metric: LandlordWinRate | SeatTeamWinRate = Field(discriminator="kind")
    baseline_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    template_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{16}$")
    name: str = Field(min_length=1, max_length=120, pattern=r"\S")
    hypothesis: str = Field(min_length=1, max_length=10000, pattern=r"\S")


class CloneExperimentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    copy_deal_seeds: bool = True
    copy_hypothesis: bool = True


class CollectExperimentRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class SaveComparisonRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120, pattern=r"\S")
    experiment_ids: list[str] = Field(min_length=2, max_length=5)
    allowed_changes: list[str] = Field(default_factory=list, max_length=32)


class ResearchEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_id: str = Field(min_length=1, max_length=128)
    note: str = Field(default="", max_length=1000)


class ResearchPuzzleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(pattern=r"^(run|probe)_[a-f0-9]{8,32}$")
    expected_report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    note: str = Field(default="", max_length=1000)


class ResearchTraceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trace_id: str = Field(min_length=1, max_length=128)
    expected_source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    note: str = Field(default="", max_length=1000)


class ResearchRevisionRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    observations: str = Field(min_length=1, max_length=10000, pattern=r"\S")
    interpretation: str = Field(default="", max_length=10000)
    limitations: str = Field(min_length=1, max_length=10000, pattern=r"\S")
    evidence: list[ResearchEvidenceRequest] = Field(default_factory=list, max_length=30)
    puzzle_evidence: list[ResearchPuzzleRequest] = Field(default_factory=list, max_length=5)
    trace_evidence: list[ResearchTraceRequest] = Field(default_factory=list, max_length=5)
