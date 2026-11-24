"""Validate saved batch selection without regenerating estimates or source data."""

from __future__ import annotations

import math
from typing import Any

from app.core.eval.puzzle import Puzzle, PuzzlePackManifest, select_spread_indices
from app.core.eval.puzzle_results import digest


def validate_selection(manifest: PuzzlePackManifest, puzzles: list[Puzzle]) -> None:
    selection = manifest.extract
    audit: dict[str, Any] = selection["selection"]
    if audit["order"] != "spread_desc_stable" or not 1 <= len(puzzles) <= 200:
        raise ValueError("Unsupported selection or citation size")
    if any(
        type(selection[k]) is not int or selection[k] < 1 for k in ("max_per_game", "max_total")
    ):
        raise ValueError("Invalid selection limits")
    threshold = selection["min_spread"]
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Invalid spread threshold")
    games, rows = audit["source_game_ids"], audit["candidates"]
    if audit["selected_game_ids"] != sorted({str(p.source["game_id"]) for p in puzzles}):
        raise ValueError("Selected game count or identity mismatch")
    if (
        not isinstance(games, list)
        or len(games) != len(set(games))
        or not all(isinstance(g, str) and g for g in games)
    ):
        raise ValueError("Invalid extraction game scope")
    if not isinstance(rows, list) or len({r["puzzle_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate selection candidates")
    for row in rows:
        if (
            not isinstance(row["puzzle_id"], str)
            or not row["puzzle_id"]
            or row["game_id"] not in games
            or type(row["spread"]) not in (int, float)
            or not math.isfinite(row["spread"])
            or row["spread"] < 0
        ):
            raise ValueError("Invalid selection candidate")
    chosen = select_spread_indices(
        [(row["spread"], row["game_id"]) for row in rows],
        min_spread=threshold,
        max_per_game=selection["max_per_game"],
        max_total=selection["max_total"],
    )
    if [rows[i]["puzzle_id"] for i in chosen] != [p.puzzle_id for p in puzzles]:
        raise ValueError("Selected positions disagree with the saved selection rule")
    checks = selection["source_checks"]
    if set(checks) != {p.puzzle_id for p in puzzles}:
        raise ValueError("Missing source checks")
    decisions = [p.source["decision_point_id"] for p in puzzles]
    if len(set(decisions)) != len(puzzles) or not all(isinstance(d, str) and d for d in decisions):
        raise ValueError("Missing or duplicate source decisions")
    for p, index in zip(puzzles, chosen, strict=True):
        check = checks[p.puzzle_id]
        if (
            not isinstance(check, dict)
            or rows[index]["game_id"] != p.source["game_id"]
            or rows[index]["spread"] != p.spread
            or p.source["experiment_id"] != manifest.source_experiment_id
            or p.evaluator_params != selection["evaluator_params"]
            or check.get("puzzle_hash") != digest(p.to_dict())
            or not isinstance(check.get("decision_hash"), str)
            or len(check["decision_hash"]) != 64
        ):
            raise ValueError("Batch provenance is incomplete or changed")
