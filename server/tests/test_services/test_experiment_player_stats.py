"""Tests for experiment per-player comparison aggregates."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.experiment_repo import ExperimentRepository


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
        await db.execute(
            """
            INSERT INTO rounds (
                game_id, round_num, player_id, action_type, prompt_tokens,
                completion_tokens, total_tokens, response_time_ms, created_at
            ) VALUES
                ('g1', 1, 'cfg_a', 'play', 10, 5, 15, 100, ?),
                ('g2', 1, 'cfg_a', 'play', 10, 5, 15, 300, ?),
                ('g1', 2, 'cfg_b', 'play', 8, 4, 12, 50, ?)
            """,
            (now, now, now),
        )
        await db.commit()


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
