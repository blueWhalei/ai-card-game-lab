"""Tests for experiment per-player comparison aggregates."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.trace_repo import TraceRepository


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "exp_compare.db")
    await init_db(path)
    return path


async def _seed(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    players = '["cfg_a","cfg_b","cfg_c"]'
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games, created_at, updated_at
            ) VALUES (?, ?, '', 'doudizhu', ?, 5, ?, ?)
            """,
            ("exp-1", "compare", players, now, now),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, data_file, created_at, experiment_id
            ) VALUES (?, 'doudizhu', 'finished', ?, 'cfg_a', 'a.jsonl', ?, 'exp-1')
            """,
            ("g1", players, now),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, data_file, created_at, experiment_id
            ) VALUES (?, 'doudizhu', 'finished', ?, 'cfg_a', 'b.jsonl', ?, 'exp-1')
            """,
            ("g2", players, now),
        )
        await db.execute(
            """
            INSERT INTO decision_points (
                id, game_id, round_number, player_id, hand_cards, game_phase,
                legal_actions, chosen_action, train_usable, created_at
            ) VALUES
                ('dp1', 'g1', 1, 'cfg_a', '[]', 'playing', '[]', '{}', 1, ?),
                ('dp2', 'g1', 2, 'cfg_a', '[]', 'playing', '[]', '{}', 1, ?),
                ('dp3', 'g1', 1, 'cfg_b', '[]', 'playing', '[]', '{}', 1, ?),
                ('dp4', 'g1', 1, 'cfg_c', '[]', 'playing', '[]', '{}', 0, ?)
            """,
            (now, now, now, now),
        )
        await db.commit()

        db.row_factory = aiosqlite.Row
        traces = TraceRepository(db)
        await traces.create_trace(
            trace_id="tr-a",
            game_id="g1",
            round_number=1,
            player_id="cfg_a",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 100},
            created_at=now,
        )
        await traces.create_trace(
            trace_id="tr-a2",
            game_id="g2",
            round_number=1,
            player_id="cfg_a",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 300},
            created_at=now,
        )
        await traces.create_trace(
            trace_id="tr-b",
            game_id="g1",
            round_number=1,
            player_id="cfg_b",
            model="m",
            prompt_version="v1",
            input_snapshot={},
            output_data={},
            metrics={"response_time_ms": 50},
            created_at=now,
        )


async def test_count_train_usable_by_player(db_path: str) -> None:
    await _seed(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = ExperimentRepository(db)
        counts = await repo.count_train_usable_by_player("exp-1")
    assert counts == {"cfg_a": 2, "cfg_b": 1}


async def test_avg_response_ms_by_player(db_path: str) -> None:
    await _seed(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        repo = ExperimentRepository(db)
        avgs = await repo.avg_response_ms_by_player("exp-1")
    assert avgs["cfg_a"] == (200.0, 2)
    assert avgs["cfg_b"] == (50.0, 1)
    assert "cfg_c" not in avgs
