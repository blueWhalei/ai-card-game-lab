"""Saved position-test records: validation, provenance and atomic publication."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.core.eval.puzzle import (
    PUZZLE_METRIC_VERSION,
    Puzzle,
    PuzzleAnswerScore,
    PuzzlePackManifest,
    summarize_answers,
)

RESULT_ID = re.compile(r"(?:run|probe)_[a-f0-9]{8,32}\Z")


class UnsupportedResultError(ValueError):
    """The metric version must not be interpreted using current definitions."""


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def pack_fingerprint(manifest: PuzzlePackManifest, puzzles: list[Puzzle]) -> str:
    return digest({"manifest": manifest.to_dict(), "puzzles": [p.to_dict() for p in puzzles]})


def pack_snapshot(manifest: PuzzlePackManifest, puzzles: list[Puzzle]) -> dict[str, Any]:
    return {
        "manifest": manifest.to_dict(),
        "puzzles": [
            {
                "puzzle_id": p.puzzle_id,
                "source": p.source,
                "evaluator_params": p.evaluator_params,
                "candidates_evaluated": p.candidates_evaluated,
                "legal_action_count": p.legal_action_count,
            }
            for p in puzzles
        ],
    }


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Invalid count")
    return value


def _measure(value: Any, *, probability: bool = False) -> None:
    if value is not None and (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value < 0
        or (probability and value > 1)
    ):
        raise ValueError("Invalid measurement")


def _score(row: dict[str, Any]) -> None:
    if row["hit"] is not None and type(row["hit"]) is not bool:
        raise ValueError("Invalid selection result")
    _measure(row["ev_loss"])
    if (row["hit"] is None) != (row["ev_loss"] is None):
        raise ValueError("Inconsistent unscored choice")


def _coverage(summary: dict[str, Any], n: int, prefix: str = "") -> None:
    evaluated = _count(summary[f"{prefix}evaluated_n"])
    if evaluated + _count(summary[f"{prefix}unevaluated_n"]) != n:
        raise ValueError("Inconsistent denominator")
    for name in ("accuracy", "mean_ev_loss"):
        value = summary[f"{prefix}{name}"]
        _measure(value, probability=name == "accuracy")
        if (value is None) != (evaluated == 0):
            raise ValueError("Missing measurement or missing denominator")


def _check_summary(summary: dict[str, Any], rows: list[dict[str, Any]], prefix: str = "") -> None:
    expected = summarize_answers(
        [PuzzleAnswerScore(row["hit"], row["ev_loss"], row["chosen_action_id"]) for row in rows]
    )
    if any(summary[f"{prefix}{key}"] != value for key, value in expected.items()):
        raise ValueError("Summary does not match saved choices")


def validate_result(report: dict[str, Any], pack_id: str, run_id: str) -> None:
    """Check stored v2 structure without rerunning a policy or changing estimates."""
    if report["pack_id"] != pack_id or report["run_id"] != run_id:
        raise ValueError("Result identity mismatch")
    if report.get("metric_version") != PUZZLE_METRIC_VERSION:
        raise UnsupportedResultError("Unsupported metric version")
    if (
        report["baseline_kind"] not in ("first", "random", "heuristic")
        or type(report["seed"]) is not int
    ):
        raise ValueError("Invalid test conditions")
    if datetime.fromisoformat(report["created_at"]).tzinfo is None:
        raise ValueError("Missing result time zone")
    summary, rows = report["summary"], report["puzzles"]
    n = _count(summary["n"])
    if not isinstance(rows, list) or len(rows) != n:
        raise ValueError("Inconsistent position count")
    ids = [row["puzzle_id"] for row in rows]
    if len(set(ids)) != n or any(not isinstance(pid, str) or not pid for pid in ids):
        raise ValueError("Duplicate or missing position identity")
    if run_id.startswith("run_"):
        _coverage(summary, n)
        if _count(summary["truncated_n"]) > n:
            raise ValueError("Invalid truncated count")
        for row in rows:
            _score(row)
            if type(row["truncated"]) is not bool:
                raise ValueError("Invalid evaluation coverage")
            if not isinstance(row["chosen_action_id"], str) or not isinstance(
                row["best_action_id"], str
            ):
                raise ValueError("Invalid action identity")
        _check_summary(summary, rows)
        if summary["truncated_n"] != sum(row["truncated"] for row in rows):
            raise ValueError("Inconsistent truncated count")
    else:
        trials = _count(summary["n_trials"])
        if trials < 1 or _count(summary["comparisons_n"]) != n * trials:
            raise ValueError("Inconsistent trial count")
        if not isinstance(summary["kinds"], list) or any(
            not isinstance(k, str) for k in summary["kinds"]
        ):
            raise ValueError("Invalid perturbation conditions")
        _coverage(summary, n * trials, "base_")
        _coverage(summary, n * trials, "pert_")
        for key in ("consistency", "repeat_consistency"):
            _measure(summary[key], probability=True)
            if (summary[key] is None) != (n == 0):
                raise ValueError("Missing comparison denominator")
        for row in rows:
            if any(
                not isinstance(row[key], str) for key in ("base_chosen_action_id", "best_action_id")
            ):
                raise ValueError("Invalid action identity")
            _score({"hit": row["base_hit"], "ev_loss": row["base_ev_loss"]})
            if [trial["trial"] for trial in row["trials"]] != list(range(trials)):
                raise ValueError("Missing or duplicate trial")
            for trial in row["trials"]:
                _score(trial)
                if any(
                    not isinstance(trial[key], str)
                    for key in ("control_action_id", "chosen_action_id")
                ):
                    raise ValueError("Invalid action identity")
                if any(type(trial[key]) is not bool for key in ("consistent", "repeat_consistent")):
                    raise ValueError("Invalid agreement result")
                if trial["consistent"] != (trial["control_action_id"] == trial["chosen_action_id"]):
                    raise ValueError("Inconsistent paired actions")
                if trial["repeat_consistent"] != (
                    trial["control_action_id"] == row["base_chosen_action_id"]
                ):
                    raise ValueError("Inconsistent repeated action")
        comparisons = [trial for row in rows for trial in row["trials"]]
        _check_summary(summary, comparisons, "pert_")
        for key, flag in (
            ("consistency", "consistent"),
            ("repeat_consistency", "repeat_consistent"),
        ):
            expected = (
                round(sum(trial[flag] for trial in comparisons) / len(comparisons), 4)
                if comparisons
                else None
            )
            if summary[key] != expected:
                raise ValueError("Summary does not match saved comparisons")
    snapshot = report.get("pack_snapshot")
    fingerprint = report.get("pack_fingerprint")
    if (snapshot is None) != (fingerprint is None):
        raise ValueError("Incomplete source snapshot")
    if snapshot is not None:
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            raise ValueError("Invalid pack fingerprint")
        if snapshot["manifest"]["pack_id"] != pack_id or snapshot["manifest"]["puzzle_count"] != n:
            raise ValueError("Source snapshot identity mismatch")
        manifest = snapshot["manifest"]
        if not isinstance(manifest["extract"], dict) or any(
            not isinstance(manifest[key], str)
            for key in ("created_at", "game_type", "source_experiment_id", "notes")
        ):
            raise ValueError("Invalid source manifest")
        if [p["puzzle_id"] for p in snapshot["puzzles"]] != ids:
            raise ValueError("Source snapshot membership mismatch")
        for point in snapshot["puzzles"]:
            if not isinstance(point["source"], dict) or not isinstance(
                point["evaluator_params"], dict
            ):
                raise ValueError("Invalid source details")
            if _count(point["candidates_evaluated"]) > _count(point["legal_action_count"]):
                raise ValueError("Invalid source evaluation count")
            if any(
                key in point["source"] and not isinstance(point["source"][key], str)
                for key in ("game_id", "decision_point_id")
            ):
                raise ValueError("Invalid source identity")


def read_result(path: Path, pack_id: str, run_id: str) -> dict[str, Any]:
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Result exceeds the supported size")
    try:
        report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        validate_result(report, pack_id, run_id)
        digest(report)
    except (OverflowError, RecursionError) as error:
        raise ValueError("Invalid result value") from error
    return report


def save_result(root: Path, report: dict[str, Any]) -> None:
    """Publish complete records exclusively; readers never see partially written JSON."""
    root.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(dir=root, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, root / f"{report['run_id']}.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
