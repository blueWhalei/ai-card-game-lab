"""Puzzle pack format, IO, answer scoring, and spread-based selection.

Packs are self-contained directories under ``{data_dir}/puzzles/{pack_id}/`` with
``manifest.json`` + ``puzzles.jsonl``. Gold labels are frozen at extract time;
this module only handles format, filtering, and offline scoring.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PUZZLE_PACK_KIND = "cardlab.puzzle_pack"
PUZZLE_SCHEMA_VERSION = 1

_MANIFEST_FILE = "manifest.json"
_PUZZLES_FILE = "puzzles.jsonl"


@dataclass(frozen=True)
class PuzzleAnswerScore:
    """Result of scoring one answer against frozen gold labels."""

    hit: bool
    ev_loss: float
    chosen_action_id: str


@dataclass
class PuzzlePackManifest:
    """Top-level metadata for a puzzle pack directory."""

    pack_id: str
    created_at: str
    game_type: str
    source_experiment_id: str
    puzzle_count: int
    extract: dict[str, Any]
    notes: str = ""
    kind: str = PUZZLE_PACK_KIND
    schema_version: int = PUZZLE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
            "pack_id": self.pack_id,
            "created_at": self.created_at,
            "game_type": self.game_type,
            "source_experiment_id": self.source_experiment_id,
            "puzzle_count": self.puzzle_count,
            "extract": self.extract,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PuzzlePackManifest:
        return cls(
            kind=str(data.get("kind", PUZZLE_PACK_KIND)),
            schema_version=int(data.get("schema_version", PUZZLE_SCHEMA_VERSION)),
            pack_id=str(data["pack_id"]),
            created_at=str(data["created_at"]),
            game_type=str(data["game_type"]),
            source_experiment_id=str(data["source_experiment_id"]),
            puzzle_count=int(data["puzzle_count"]),
            extract=dict(data.get("extract", {})),
            notes=str(data.get("notes", "")),
        )


@dataclass
class Puzzle:
    """One frozen decision point with precomputed action values."""

    puzzle_id: str
    game_type: str
    source: dict[str, Any]
    observation: dict[str, Any]
    legal_actions: list[dict[str, Any]]
    action_values: dict[str, float]
    best_action_id: str
    spread: float
    candidates_evaluated: int
    legal_action_count: int
    truncated: bool
    evaluator_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "puzzle_id": self.puzzle_id,
            "game_type": self.game_type,
            "source": self.source,
            "observation": self.observation,
            "legal_actions": self.legal_actions,
            "action_values": self.action_values,
            "best_action_id": self.best_action_id,
            "spread": self.spread,
            "candidates_evaluated": self.candidates_evaluated,
            "legal_action_count": self.legal_action_count,
            "truncated": self.truncated,
            "evaluator_params": self.evaluator_params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Puzzle:
        raw_values = data.get("action_values", {})
        return cls(
            puzzle_id=str(data["puzzle_id"]),
            game_type=str(data["game_type"]),
            source=dict(data.get("source", {})),
            observation=dict(data.get("observation", {})),
            legal_actions=list(data.get("legal_actions", [])),
            action_values={str(k): float(v) for k, v in raw_values.items()},
            best_action_id=str(data["best_action_id"]),
            spread=float(data["spread"]),
            candidates_evaluated=int(data["candidates_evaluated"]),
            legal_action_count=int(data["legal_action_count"]),
            truncated=bool(data["truncated"]),
            evaluator_params=dict(data.get("evaluator_params", {})),
        )


def score_answer(
    best_action_id: str,
    action_values: dict[str, float],
    chosen_action_id: str,
) -> PuzzleAnswerScore:
    """Score a chosen action against frozen gold labels."""
    best = float(action_values[best_action_id])
    spread = max(action_values.values()) - min(action_values.values())
    if chosen_action_id not in action_values:
        return PuzzleAnswerScore(False, spread, chosen_action_id)
    chosen = float(action_values[chosen_action_id])
    return PuzzleAnswerScore(
        hit=chosen_action_id == best_action_id,
        ev_loss=round(best - chosen, 6),
        chosen_action_id=chosen_action_id,
    )


def select_by_spread(
    candidates: list[Puzzle],
    *,
    min_spread: float,
    max_per_game: int,
    max_total: int,
) -> list[Puzzle]:
    """Keep high-spread puzzles with per-game and pack-wide caps."""
    eligible = [p for p in candidates if p.spread >= min_spread]
    eligible.sort(key=lambda p: p.spread, reverse=True)

    per_game: dict[str, int] = defaultdict(int)
    picked: list[Puzzle] = []
    for puzzle in eligible:
        if len(picked) >= max_total:
            break
        game_id = str(puzzle.source.get("game_id", ""))
        if per_game[game_id] >= max_per_game:
            continue
        per_game[game_id] += 1
        picked.append(puzzle)
    return picked


def save_pack(root: Path, manifest: PuzzlePackManifest, puzzles: list[Puzzle]) -> None:
    """Write manifest.json and puzzles.jsonl under *root*."""
    root.mkdir(parents=True, exist_ok=True)
    manifest_payload = PuzzlePackManifest(
        pack_id=manifest.pack_id,
        created_at=manifest.created_at,
        game_type=manifest.game_type,
        source_experiment_id=manifest.source_experiment_id,
        puzzle_count=len(puzzles),
        extract=manifest.extract,
        notes=manifest.notes,
        kind=manifest.kind,
        schema_version=manifest.schema_version,
    )
    manifest_path = root / _MANIFEST_FILE
    manifest_path.write_text(
        json.dumps(manifest_payload.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    puzzles_path = root / _PUZZLES_FILE
    lines = [json.dumps(p.to_dict(), ensure_ascii=False) for p in puzzles]
    puzzles_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_pack(root: Path) -> tuple[PuzzlePackManifest, list[Puzzle]]:
    """Load a puzzle pack; reject wrong kind or schema version."""
    manifest_path = root / _MANIFEST_FILE
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if raw.get("kind") != PUZZLE_PACK_KIND:
        msg = f"expected kind {PUZZLE_PACK_KIND!r}, got {raw.get('kind')!r}"
        raise ValueError(msg)
    if raw.get("schema_version") != PUZZLE_SCHEMA_VERSION:
        msg = f"expected schema_version {PUZZLE_SCHEMA_VERSION}, got {raw.get('schema_version')!r}"
        raise ValueError(msg)

    manifest = PuzzlePackManifest.from_dict(raw)
    puzzles_path = root / _PUZZLES_FILE
    puzzles: list[Puzzle] = []
    if puzzles_path.exists():
        for line in puzzles_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                puzzles.append(Puzzle.from_dict(json.loads(stripped)))
    return manifest, puzzles
