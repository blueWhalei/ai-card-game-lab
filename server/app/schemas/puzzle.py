"""Puzzle pack HTTP schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PuzzleExtractRequest(BaseModel):
    experiment_id: str
    min_spread: float = 0.15
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
