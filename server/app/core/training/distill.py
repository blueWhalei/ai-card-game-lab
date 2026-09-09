"""Build distillation preference pairs (teacher action vs student action)."""

from __future__ import annotations

import json
from typing import Any, Literal

DistillSkip = Literal[
    "missing_prompt",
    "missing_action",
    "tie",
    "missing_seed",
    "seat_mismatch",
    "unpaired",
]


def normalize_game_row(row: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON columns on a raw games row."""
    out = dict(row)
    raw_players = out.get("player_ids")
    if isinstance(raw_players, str):
        try:
            out["player_ids"] = json.loads(raw_players)
        except json.JSONDecodeError:
            out["player_ids"] = []
    raw_meta = out.get("metadata")
    if isinstance(raw_meta, str):
        try:
            out["metadata"] = json.loads(raw_meta)
        except json.JSONDecodeError:
            out["metadata"] = {}
    return out


def seat_index_of(player_ids: list[str], player_id: str) -> int | None:
    """Return seat index or ``None`` when the player is not seated."""
    try:
        return list(player_ids).index(player_id)
    except ValueError:
        return None


def build_distill_pair(
    teacher: dict[str, Any],
    student: dict[str, Any],
    *,
    include_thinking: bool = False,
) -> tuple[dict[str, Any] | None, DistillSkip | None]:
    """Return one distill record or a skip reason."""
    prompt = student.get("prompt_messages")
    if not isinstance(prompt, list) or not prompt:
        return None, "missing_prompt"

    teacher_id = str(teacher.get("action_id") or "")
    student_id = str(student.get("action_id") or "")
    if not teacher_id or not student_id:
        return None, "missing_action"
    if teacher_id == student_id:
        return None, "tie"

    chosen = json.dumps({"action_id": teacher_id}, ensure_ascii=False)
    rejected_payload: dict[str, str] = {"action_id": student_id}
    if include_thinking:
        rejected_payload["thinking"] = str(student.get("thinking") or "")
    rejected = json.dumps(rejected_payload, ensure_ascii=False)

    return {
        "messages": list(prompt),
        "chosen": chosen,
        "rejected": rejected,
        "metadata": {
            "teacher_decision_id": teacher.get("id"),
            "student_decision_id": student.get("id"),
            "teacher_game_id": teacher.get("game_id"),
            "student_game_id": student.get("game_id"),
            "round_number": student.get("round_number"),
            "deal_seed": student.get("_deal_seed"),
            "seat_index": student.get("_seat_index"),
            "teacher_action_id": teacher_id,
            "student_action_id": student_id,
        },
    }, None


def index_decisions_by_match_key(
    items: list[dict[str, Any]],
    games_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[tuple[int, int, int], dict[str, Any]], dict[str, int]]:
    """Map ``(deal_seed, round, seat_index)`` → enriched decision.

    Returns ``(index, skip_counts)``.
    """
    index: dict[tuple[int, int, int], dict[str, Any]] = {}
    skips = {
        "missing_seed": 0,
        "seat_mismatch": 0,
        "missing_action": 0,
    }
    for item in items:
        game = games_by_id.get(str(item.get("game_id") or ""))
        if not isinstance(game, dict):
            skips["missing_seed"] += 1
            continue
        meta = game.get("metadata") if isinstance(game.get("metadata"), dict) else {}
        raw_seed = meta.get("deal_seed") if isinstance(meta, dict) else None
        if raw_seed is None:
            skips["missing_seed"] += 1
            continue
        try:
            deal_seed = int(raw_seed)
        except (TypeError, ValueError):
            skips["missing_seed"] += 1
            continue
        player_ids = game.get("player_ids")
        if not isinstance(player_ids, list):
            skips["seat_mismatch"] += 1
            continue
        seat = seat_index_of([str(p) for p in player_ids], str(item.get("player_id") or ""))
        if seat is None:
            skips["seat_mismatch"] += 1
            continue
        if not str(item.get("action_id") or ""):
            skips["missing_action"] += 1
            continue
        round_number = int(item.get("round_number") or 0)
        enriched = dict(item)
        enriched["_deal_seed"] = deal_seed
        enriched["_seat_index"] = seat
        enriched["_seat_count"] = len(player_ids)
        index[(deal_seed, round_number, seat)] = enriched
    return index, skips


def pair_distill_indexes(
    teacher_index: dict[tuple[int, int, int], dict[str, Any]],
    student_index: dict[tuple[int, int, int], dict[str, Any]],
    *,
    include_thinking: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Join teacher/student indexes; skip seat-count mismatches and ties."""
    records: list[dict[str, Any]] = []
    meta = {
        "skipped_tie": 0,
        "skipped_missing_prompt": 0,
        "skipped_missing_action": 0,
        "skipped_seat_mismatch": 0,
        "skipped_unpaired": 0,
        "matched_keys": 0,
    }
    for key, student in student_index.items():
        teacher = teacher_index.get(key)
        if teacher is None:
            meta["skipped_unpaired"] += 1
            continue
        meta["matched_keys"] += 1
        if int(teacher.get("_seat_count") or 0) != int(student.get("_seat_count") or 0):
            meta["skipped_seat_mismatch"] += 1
            continue
        record, skip = build_distill_pair(
            teacher, student, include_thinking=include_thinking
        )
        if record is not None:
            records.append(record)
            continue
        if skip == "tie":
            meta["skipped_tie"] += 1
        elif skip == "missing_prompt":
            meta["skipped_missing_prompt"] += 1
        elif skip == "missing_action":
            meta["skipped_missing_action"] += 1
        else:
            meta["skipped_unpaired"] += 1
    return records, meta


__all__ = [
    "DistillSkip",
    "build_distill_pair",
    "index_decisions_by_match_key",
    "normalize_game_row",
    "pair_distill_indexes",
    "seat_index_of",
]
