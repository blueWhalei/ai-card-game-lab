"""Scope and freeze exploratory position tests without changing comparison statistics."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiosqlite

from app.core.research.decision_alignment import comparison_members
from app.repositories.decision_repo import DecisionRepository
from app.repositories.research_repo import ResearchRepository
from app.services.puzzle_service import PuzzleService
from app.utils.exceptions import AppError


async def checked_puzzle(
    db: aiosqlite.Connection,
    puzzles: PuzzleService,
    pack_id: str,
    run_id: str,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    result, positions = await asyncio.to_thread(puzzles.citation_result, pack_id, run_id)
    report = result["report"]
    saved = report["pack_snapshot"]
    selection = saved["manifest"]["extract"]
    frozen_sources = []
    try:
        for point, position in zip(saved["puzzles"], positions, strict=True):
            source = point["source"]
            decision = await DecisionRepository(db).get_by_id(source["decision_point_id"])
            if (
                decision is None
                or decision["game_id"] != source["game_id"]
                or decision["created_at"] != source["decision_created_at"]
            ):
                raise ValueError("source changed")
            if selection["method"] == "decision_record":
                current = await puzzles.decision_source(decision["id"])
                if (
                    decision["evaluator_params"] != point["evaluator_params"]
                    or current["source_hash"] != selection["source"]["source_hash"]
                ):
                    raise ValueError("source estimates changed")
            else:
                current = await puzzles.batch_source(position)
                if (
                    current["decision_hash"]
                    != selection["source_checks"][position.puzzle_id]["decision_hash"]
                ):
                    raise ValueError("source decision changed")
            if any(current.get(key) != value for key, value in source.items()):
                raise ValueError("source identity changed")
            frozen_sources.append({"decision": {key: decision.get(key) for key in fields}})
    except (KeyError, ValueError, TypeError, AppError) as error:
        raise AppError(
            "测试来源不属于冻结共同样本，或原决策与评估条件已变化", "RESEARCH_PUZZLE_SCOPE", 422
        ) from error
    return {
        "result": result,
        "sources": frozen_sources,
    }


def check_puzzle_scope(preview: dict[str, Any], snapshot: dict[str, Any]) -> None:
    """Check every verified source against one frozen cohort, without replaying again."""
    try:
        members = comparison_members(snapshot["result"])
        points = preview["result"]["report"]["pack_snapshot"]["puzzles"]
        for point in points:
            source = point["source"]
            origin = [
                (owner, member["seed"])
                for member in members
                for owner, gid in member["game_ids"].items()
                if gid == source["game_id"]
            ]
            if (
                origin != [(source["experiment_id"], source["deal_seed"])]
                or source["decision_created_at"] > snapshot["result"]["computed_at"]
            ):
                raise ValueError("out of scope")
    except (KeyError, TypeError, ValueError) as error:
        raise AppError(
            "测试的全部来源不属于冻结共同样本范围", "RESEARCH_PUZZLE_SCOPE", 422
        ) from error


async def preview_puzzle(
    db: aiosqlite.Connection,
    puzzles: PuzzleService,
    snapshot: dict[str, Any],
    pack_id: str,
    run_id: str,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    preview = await checked_puzzle(db, puzzles, pack_id, run_id, fields)
    check_puzzle_scope(preview, snapshot)
    return preview


async def freeze_puzzles(
    db: aiosqlite.Connection,
    puzzles: PuzzleService,
    snapshot: dict[str, Any],
    requests: list[dict[str, str]],
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    ids = [(item["pack_id"], item["run_id"]) for item in requests]
    if len(ids) > 5 or len(set(ids)) != len(ids):
        raise AppError("每版最多引用 5 条测试，同一测试只能引用一次", "RESEARCH_PUZZLE_LIMIT", 422)
    frozen = []
    size = 0
    for item in requests:
        preview = await preview_puzzle(
            db, puzzles, snapshot, item["pack_id"], item["run_id"], fields
        )
        if preview["result"]["report_hash"] != item["expected_report_hash"]:
            raise AppError(
                "测试记录在预览后发生变化，请重新查阅后再引用；草稿未被覆盖",
                "RESEARCH_PUZZLE_CHANGED",
                409,
            )
        citation = {"note": item["note"].strip(), **preview}
        size += len(json.dumps(citation, ensure_ascii=False).encode())
        if size > 8 * 1024 * 1024:
            raise AppError(
                "测试引用内容超过 8 MiB，请减少引用后再发布", "RESEARCH_PUZZLE_LIMIT", 422
            )
        frozen.append(citation)
    return frozen


async def puzzle_statuses(
    db: aiosqlite.Connection, puzzles: PuzzleService, evidence: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    statuses = []
    for item in evidence:
        saved = item["result"]
        report = saved["report"]
        state: dict[str, Any] = {"record_status": "missing", "source_status": None}
        try:
            current = await asyncio.to_thread(puzzles.result, report["pack_id"], report["run_id"])
            state.update(
                record_status="available"
                if current["report_hash"] == saved["report_hash"]
                else "changed",
                source_status=current["source_status"],
            )
        except AppError as error:
            state["record_status"] = (
                "missing"
                if error.status_code == 404
                else "unsupported"
                if error.code == "PUZZLE_RESULT_UNSUPPORTED"
                else "invalid"
            )
        state["decisions"] = await ResearchRepository(db).evidence_status(item["sources"])
        statuses.append(state)
    return statuses
