"""Tests for cross-experiment comparison aggregates."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.trace_repo import TraceRepository
from app.services.experiment_service import ExperimentService


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "exp_bench.db")
    await init_db(path)
    return path


async def _seed_pair(db_path: str) -> tuple[str, str]:
    now = datetime.now(tz=UTC).isoformat()
    players = '["cfg_a","cfg_b","cfg_c"]'
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games, created_at, updated_at
            ) VALUES
                ('exp-base', '基线', '', 'doudizhu', ?, 5, ?, ?),
                ('exp-lora', '对照', '', 'doudizhu', ?, 5, ?, ?)
            """,
            (players, now, now, players, now, now),
        )
        await db.execute(
            "UPDATE experiments SET protocol = ?",
            (
                '{"schema_version":2,"dataset":{"deal_seeds":[]},"solver":{},"scorer":{},"engine":{}}',
            ),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, total_rounds,
                data_file, created_at, experiment_id
            ) VALUES
                ('g-base', 'doudizhu', 'finished', ?, 'cfg_a', 20, 'a.jsonl', ?, 'exp-base'),
                ('g-lora', 'doudizhu', 'finished', ?, 'cfg_b', 18, 'b.jsonl', ?, 'exp-lora')
            """,
            (players, now, players, now),
        )
        await db.execute(
            """UPDATE games SET winner_role = 'landlord', metadata = json_object('landlord_id', winner_id)"""
        )
        await db.execute(
            """
            INSERT INTO rounds (
                game_id, round_num, player_id, action_type, prompt_tokens,
                completion_tokens, total_tokens, response_time_ms, created_at
            ) VALUES
                ('g-base', 1, 'cfg_a', 'play', 10, 5, 15, 200, ?),
                ('g-lora', 1, 'cfg_b', 'play', 20, 10, 30, 80, ?)
            """,
            (now, now),
        )
        await db.execute(
            """
            INSERT INTO decision_points (
                id, game_id, round_number, player_id, hand_cards, game_phase,
                legal_actions, chosen_action, train_usable, created_at
            ) VALUES
                ('dp-b1', 'g-base', 1, 'cfg_a', '[]', 'playing', '[]', '{}', 1, ?),
                ('dp-b2', 'g-base', 2, 'cfg_a', '[]', 'playing', '[]', '{}', 0, ?),
                ('dp-l1', 'g-lora', 1, 'cfg_b', '[]', 'playing', '[]', '{}', 1, ?)
            """,
            (now, now, now),
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        traces = TraceRepository(db)
        await traces.create_trace(
            trace_id="tr-base",
            game_id="g-base",
            round_number=1,
            player_id="cfg_a",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 200, "parser_ok": 0},
            created_at=now,
        )
        await traces.create_trace(
            trace_id="tr-lora",
            game_id="g-lora",
            round_number=1,
            player_id="cfg_b",
            model="m",
            prompt_version="v2",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 80, "parser_ok": 1},
            created_at=now,
        )
    return "exp-base", "exp-lora"


class _FakeGameService:
    def player_slots(self, game_type: str) -> tuple[int, int]:
        return (3, 3)


async def test_report_keeps_snapshot_hypothesis_after_run_notes_change(db_path: str) -> None:
    await _seed_pair(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE experiments SET hypothesis='Frozen hypothesis'")
        await db.commit()
    service = ExperimentService(sqlite_path=db_path, game_service=_FakeGameService())  # type: ignore[arg-type]
    snapshot = await service.save_comparison(["exp-base", "exp-lora"], "Readable report", [])
    version = await service.save_research(
        snapshot["id"], 0, "Observed", "Possible interpretation", "No valid pairs", []
    )
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE experiments SET hypothesis='Changed later'")
        await db.commit()
    report = await service.get_research(version["record"]["id"], export=True)
    assert report["comparison"] == snapshot
    assert all(
        row["hypothesis"] == "Frozen hypothesis"
        for row in report["comparison"]["result"]["experiments"]
    )
    assert report["record"]["limitations"] == "No valid pairs"
    assert report["record"]["evidence"] == []


async def test_compare_aggregates_rates_and_ci(db_path: str) -> None:
    await _seed_pair(db_path)
    service = ExperimentService(sqlite_path=db_path, game_service=_FakeGameService())  # type: ignore[arg-type]
    payload = await service.compare_experiments(["exp-base", "exp-lora"])
    by_id = {item["id"]: item for item in payload["experiments"]}

    base = by_id["exp-base"]
    lora = by_id["exp-lora"]
    assert base["decision_count"] == 2
    assert base["train_usable_rate"] == 0.5
    assert base["parser_success_rate"] == 0.0
    assert base["total_tokens"] == 15
    assert lora["train_usable_rate"] == 1.0
    assert lora["parser_success_rate"] == 1.0
    assert lora["total_tokens"] == 30

    winner_stat = next(s for s in base["player_stats"] if s["player_id"] == "cfg_a")
    low, high = winner_stat["win_rate_ci"]
    assert winner_stat["win_rate"] == 1.0
    assert 0.0 <= low < 1.0
    assert high == 1.0
