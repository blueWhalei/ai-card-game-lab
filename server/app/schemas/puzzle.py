"""Puzzle pack HTTP schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DecisionPuzzleRequest(BaseModel):
    decision_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)
    expected_source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A test question is required")
        return value.strip()


class PuzzleExtractRequest(BaseModel):
    experiment_id: str
    min_spread: float = Field(default=0.15, ge=0, allow_inf_nan=False)
    max_per_game: int = Field(default=3, ge=1)
    max_total: int = Field(default=200, ge=0)


class PuzzleRunRequest(BaseModel):
    baseline_kind: Literal["first", "random", "heuristic"] = Field(
        default="heuristic",
        description="Non-LLM baseline: first, random or heuristic.",
    )
    seed: int = 0


class PuzzleProbeRequest(BaseModel):
    baseline_kind: Literal["first", "random", "heuristic"] = Field(
        default="heuristic",
        description="Non-LLM baseline: first, random or heuristic.",
    )
    seed: int = 0
    n_trials: int = Field(default=3, ge=1, le=50)
    kinds: list[Literal["shuffle_legal_actions", "shuffle_hand_cards"]] | None = None


class PuzzlePackSummary(BaseModel):
    pack_id: str
    created_at: str
    game_type: str
    source_experiment_id: str
    puzzle_count: int
    extract: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    kind: str = "cardlab.puzzle_pack"
    schema_version: int = 1
