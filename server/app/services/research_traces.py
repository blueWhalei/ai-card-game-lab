"""Freeze recorded invocations as diagnostic evidence, never as additional samples."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.core.research.decision_alignment import comparison_members
from app.repositories.game_repo import GameRepository
from app.repositories.trace_repo import TraceRepository
from app.utils.exceptions import AppError

MAX_TRACE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone missing")
    return result.astimezone(UTC)


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


async def checked_trace(db: aiosqlite.Connection, trace_id: str) -> dict[str, Any]:
    try:
        repo = TraceRepository(db)
        trace = await repo.get_by_id(trace_id)
        if trace is None:
            raise AppError("调用记录已不存在", "RESEARCH_TRACE_MISSING", 404)
        trace["spans"] = await repo.get_spans(trace_id)
        game = await GameRepository(db).get_by_id(trace["game_id"])
        players = json.loads(game["player_ids"])
        metadata = json.loads(game["metadata"])
        source = {
            "experiment_id": game["experiment_id"],
            "game_id": game["id"],
            "game_type": game["game_type"],
            "player_ids": players,
            "deal_seed": metadata.get("deal_seed"),
            "created_at": game["created_at"],
            "status": game["status"],
        }
        if (
            not source["experiment_id"]
            or game["status"] != "finished"
            or type(source["deal_seed"]) is not int
            or not isinstance(players, list)
            or trace["player_id"] not in players
            or type(trace["round_number"]) is not int
            or trace["round_number"] < 0
            or any(
                not isinstance(trace[key], dict)
                for key in ("input_snapshot", "output_data", "metrics")
            )
        ):
            raise ValueError("Invalid source identity")
        _time(trace["created_at"])
        _time(source["created_at"])
        for span in trace["spans"]:
            if span["data"] is not None and not isinstance(span["data"], dict):
                raise ValueError("Invalid span data")
            _time(span["start_time"])
            if span["end_time"] is not None:
                if _time(span["end_time"]) < _time(span["start_time"]):
                    raise ValueError("Invalid span interval")
        payload = {"trace": trace, "source": source}
        encoded = _encoded(payload)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise AppError("调用内容或对局来源无法核对", "RESEARCH_TRACE_INVALID", 422) from error
    if len(encoded) > MAX_TRACE_BYTES:
        raise AppError("单条调用引用超过 2 MiB，未截断内容", "RESEARCH_TRACE_LIMIT", 422)
    return {**payload, "source_hash": hashlib.sha256(encoded).hexdigest()}


def check_trace_scope(preview: dict[str, Any], snapshot: dict[str, Any]) -> None:
    try:
        trace, source = preview["trace"], preview["source"]
        result = snapshot["result"]
        origins = [
            (owner, member["seed"])
            for member in comparison_members(result)
            for owner, gid in member["game_ids"].items()
            if gid == trace["game_id"]
        ]
        owners = [row for row in result["experiments"] if row["id"] == source["experiment_id"]]
        cutoff = _time(result["computed_at"])
        if (
            result.get("metric_version") != "paired-cohort-v5"
            or origins != [(source["experiment_id"], source["deal_seed"])]
            or len(owners) != 1
            or owners[0]["game_type"] != source["game_type"]
            or owners[0]["player_ids"] != source["player_ids"]
            or _time(source["created_at"]) > cutoff
            or _time(trace["created_at"]) > cutoff
            or any(
                _time(span[key]) > cutoff
                for span in trace["spans"]
                for key in ("start_time", "end_time")
                if span[key] is not None
            )
        ):
            raise ValueError("Outside frozen cohort")
    except (ValueError, TypeError, KeyError) as error:
        raise AppError(
            "调用来源不属于该比较的冻结共同样本或时间范围", "RESEARCH_TRACE_SCOPE", 422
        ) from error


async def preview_trace(
    db: aiosqlite.Connection, snapshot: dict[str, Any], trace_id: str
) -> dict[str, Any]:
    preview = await checked_trace(db, trace_id)
    check_trace_scope(preview, snapshot)
    return {
        **preview,
        "comparison_id": snapshot["id"],
        "cutoff": snapshot["result"]["computed_at"],
        "read_at": datetime.now(UTC).isoformat(),
    }


async def freeze_traces(
    db: aiosqlite.Connection, snapshot: dict[str, Any], requests: list[dict[str, str]]
) -> list[dict[str, Any]]:
    ids = [item["trace_id"] for item in requests]
    if len(ids) > 5 or len(ids) != len(set(ids)):
        raise AppError("每版最多引用 5 条调用，同一记录只能引用一次", "RESEARCH_TRACE_LIMIT", 422)
    frozen = []
    size = 0
    for item in requests:
        preview = await preview_trace(db, snapshot, item["trace_id"])
        if preview["source_hash"] != item["expected_source_hash"]:
            raise AppError(
                "调用记录在预览后发生变化，请重新查阅后明确更新引用；草稿未被覆盖",
                "RESEARCH_TRACE_CHANGED",
                409,
            )
        citation = {**preview, "note": item["note"].strip()}
        size += len(_encoded(citation))
        if size > MAX_TOTAL_BYTES:
            raise AppError("调用引用总内容超过 8 MiB，请减少引用", "RESEARCH_TRACE_LIMIT", 422)
        frozen.append(citation)
    return frozen


async def trace_statuses(
    db: aiosqlite.Connection, evidence: list[dict[str, Any]]
) -> dict[str, str]:
    statuses = {}
    for item in evidence:
        saved = item["trace"]
        try:
            current = await checked_trace(db, saved["id"])
            if current["source"] != item["source"] or any(
                current["trace"][key] != saved[key]
                for key in ("game_id", "player_id", "round_number", "created_at")
            ):
                state = "identity_mismatch"
            else:
                state = "available" if current["source_hash"] == item["source_hash"] else "changed"
        except AppError as error:
            state = "missing" if error.status_code == 404 else "invalid"
        statuses[saved["id"]] = state
    return statuses
