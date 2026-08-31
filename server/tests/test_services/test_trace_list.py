"""Tests for composeable trace list and metrics filters."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.trace_repo import TraceRepository


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "traces.db")
    await init_db(path)
    return path


async def _seed_game_and_traces(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games, created_at, updated_at
            ) VALUES (?, ?, '', 'doudizhu', ?, 3, ?, ?)
            """,
            ("exp-1", "exp", '["p1","p2","p3"]', now, now),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, data_file, created_at, experiment_id
            ) VALUES (?, 'doudizhu', 'finished', ?, 'x.jsonl', ?, ?)
            """,
            ("game-exp", '["p1","p2","p3"]', now, "exp-1"),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, data_file, created_at, experiment_id
            ) VALUES (?, 'doudizhu', 'finished', ?, 'y.jsonl', ?, NULL)
            """,
            ("game-other", '["p1","p2","p3"]', now),
        )
        await db.commit()

        db.row_factory = aiosqlite.Row
        repo = TraceRepository(db)
        await repo.create_trace(
            trace_id="tr-exp-p1",
            game_id="game-exp",
            round_number=1,
            player_id="p1",
            model="model-a",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 100},
            created_at=now,
        )
        await repo.create_trace(
            trace_id="tr-exp-p2",
            game_id="game-exp",
            round_number=2,
            player_id="p2",
            model="model-b",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 200},
            created_at=now,
        )
        await repo.create_trace(
            trace_id="tr-other",
            game_id="game-other",
            round_number=1,
            player_id="p1",
            model="model-a",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 50},
            created_at=now,
        )


async def test_list_filtered_experiment_and_player(db_path: str) -> None:
    await _seed_game_and_traces(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = TraceRepository(db)
        rows, total = await repo.list_filtered(experiment_id="exp-1", player_id="p1")
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["id"] == "tr-exp-p1"


async def test_list_filtered_experiment_and_model(db_path: str) -> None:
    await _seed_game_and_traces(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = TraceRepository(db)
        rows, total = await repo.list_filtered(experiment_id="exp-1", model="model-b")
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["id"] == "tr-exp-p2"


async def test_metrics_scoped_to_experiment(db_path: str) -> None:
    await _seed_game_and_traces(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = TraceRepository(db)
        metrics = await repo.get_metrics(experiment_id="exp-1")
    assert metrics["total_traces"] == 2
    assert metrics["avg_response_time_ms"] == 150.0


async def test_list_filtered_parser_ok(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = TraceRepository(db)
        await repo.create_trace(
            trace_id="tr-ok",
            game_id="g1",
            round_number=1,
            player_id="p1",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 10, "used_langchain_parser": True},
            created_at=now,
        )
        await repo.create_trace(
            trace_id="tr-fail",
            game_id="g1",
            round_number=2,
            player_id="p1",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 20, "used_langchain_parser": False},
            created_at=now,
        )
        ok_rows, ok_total = await repo.list_filtered(parser_ok=True)
        fail_rows, fail_total = await repo.list_filtered(parser_ok=False)
    assert ok_total == 1 and ok_rows[0]["id"] == "tr-ok"
    assert fail_total == 1 and fail_rows[0]["id"] == "tr-fail"


async def test_list_recent_returns_traces_without_game_filter(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = TraceRepository(db)
        await repo.create_trace(
            trace_id="tr-1",
            game_id="game-1",
            round_number=1,
            player_id="p1",
            model="deepseek-v4-flash",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 12},
            created_at=now,
        )
        rows = await repo.list_recent(limit=10, offset=0)

    assert len(rows) == 1
    assert rows[0]["id"] == "tr-1"
    assert rows[0]["game_id"] == "game-1"


async def test_version_stats_empty_version_does_not_divide_none(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = TraceRepository(db)
        stats = await repo.get_version_stats("missing")
    assert stats["total_traces"] == 0
    assert stats["langchain_success_count"] == 0
    assert stats["avg_response_time_ms"] == 0.0
    assert stats["success_rate"] == 0.0
