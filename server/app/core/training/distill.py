"""Build distillation preference pairs (teacher action vs student action)."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Literal

from app.core.research.decision_alignment import align_decisions, decision_context
from app.core.stats.comparison import seed_value

DistillSkip = Literal[
    "missing_prompt",
    "missing_action",
    "tie",
    "missing_seed",
    "seat_mismatch",
    "unpaired",
    "invalid_context",
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
    seats: list[list[str]],
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
    try:
        if decision_context(teacher, seats[0]) != decision_context(student, seats[1]):
            return None, "invalid_context"
    except (KeyError, TypeError, ValueError, IndexError):
        return None, "invalid_context"
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
            "preference_source": "teacher_choice",
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


def pair_distill_decisions(
    teacher_items: list[dict[str, Any]],
    student_items: list[dict[str, Any]],
    teacher_games: dict[str, dict[str, Any]],
    student_games: dict[str, dict[str, Any]],
    *,
    include_thinking: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Export only the first divergence after a continuous verified history.

    Exclusion counts describe student decision records. Duplicate deal seeds
    are ambiguous even when only one of their games has usable decisions.
    """
    meta = dict.fromkeys(
        ["matched_keys"]
        + [
            f"skipped_{reason}"
            for reason in (
                "tie",
                "missing_prompt",
                "missing_action",
                "seat_mismatch",
                "unpaired",
                "missing_seed",
                "duplicate_seed",
                "incomplete_game",
                "invalid_context",
                "different_path",
            )
        ],
        0,
    )
    grouped: list[dict[str, list[dict[str, Any]]]] = []
    for items in (teacher_items, student_items):
        by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            by_game[str(item["game_id"])].append(item)
        grouped.append(by_game)
    indexes: list[dict[int, list[dict[str, Any]]]] = []
    for games in (teacher_games, student_games):
        by_seed: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for game in games.values():
            seed = seed_value((game.get("metadata") or {}).get("deal_seed"))
            if seed is not None:
                by_seed[seed].append(game)
        indexes.append(by_seed)
    records = []
    for gid, students in grouped[1].items():
        game = student_games.get(gid)
        seed = seed_value((game.get("metadata") or {}).get("deal_seed")) if game else None
        if seed is None:
            meta["skipped_missing_seed"] += len(students)
            continue
        left, right = indexes[0].get(seed, []), indexes[1].get(seed, [])
        if len(left) > 1 or len(right) > 1:
            meta["skipped_duplicate_seed"] += len(students)
            continue
        if not left:
            meta["skipped_unpaired"] += len(students)
            continue
        games = [left[0], right[0]]
        seats = [g.get("player_ids") or [] for g in games]
        if (
            not games[0].get("game_type")
            or games[0]["game_type"] != games[1].get("game_type")
            or any(not isinstance(s, list) or len(s) < 2 or len(set(s)) != len(s) for s in seats)
            or len(seats[0]) != len(seats[1])
        ):
            meta["skipped_seat_mismatch"] += len(students)
            continue
        totals = [g.get("total_rounds") for g in games]
        if any(g.get("status") != "finished" for g in games) or any(
            type(n) is not int or not 0 < n <= 2000 for n in totals
        ):
            meta["skipped_incomplete_game"] += len(students)
            continue
        teachers = grouped[0].get(str(games[0]["id"]), [])
        sequences = [teachers, students]
        if any(
            type(point.get("round_number")) is not int or not 0 <= point["round_number"] < total
            for sequence, total in zip(sequences, totals, strict=True)
            for point in sequence
        ):
            meta["skipped_invalid_context"] += len(students)
            continue
        alignment = align_decisions(teachers, students, seats, totals)
        teacher_by_id = {point["id"]: point for point in teachers}
        for student in students:
            frame = alignment["frames"][student["round_number"]]
            status = frame["status"]
            if frame["left"] and frame["right"]:
                meta["matched_keys"] += 1
            if status == "same":
                meta["skipped_tie"] += 1
            elif status == "divergence":
                teacher = teacher_by_id[frame["left"]["id"]]
                enriched = {
                    **student,
                    "_deal_seed": seed,
                    "_seat_index": seats[1].index(student["player_id"]),
                }
                record, skip = build_distill_pair(
                    teacher, enriched, seats=seats, include_thinking=include_thinking
                )
                if record is not None:
                    records.append(record)
                else:
                    meta[f"skipped_{skip}"] += 1
            else:
                reason = "different_path" if status == "different_path" else "invalid_context"
                meta[f"skipped_{reason}"] += 1
    return records, meta
