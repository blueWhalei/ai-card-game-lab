"""Tests for restart recovery of orphaned games and training tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.game_repo import GameRepository
from app.repositories.training_repo import TrainingTaskRepository
from app.services.startup_recovery import recover_orphaned_runtime


@pytest.fixture
async def sqlite_path(tmp_path: Path) -> str:
    path = str(tmp_path / "recover.db")
    await init_db(path)
    return path


async def test_recover_orphaned_games_and_training_tasks(sqlite_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    async with aiosqlite.connect(sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        games = GameRepository(db)
        await games.create(
            game_id="game-running",
            game_type="doudizhu",
            player_ids=["a", "b", "c"],
            data_file="games/game-running.jsonl",
            created_at=now,
            status="running",
        )
        await games.create(
            game_id="game-paused",
            game_type="doudizhu",
            player_ids=["a", "b", "c"],
            data_file="games/game-paused.jsonl",
            created_at=now,
            status="paused",
        )
        await games.create(
            game_id="game-finished",
            game_type="doudizhu",
            player_ids=["a", "b", "c"],
            data_file="games/game-finished.jsonl",
            created_at=now,
            status="finished",
        )
        tasks = TrainingTaskRepository(db)
        await tasks.create(
            {
                "id": "task-training",
                "name": "orphan",
                "dataset_id": "ds-1",
                "base_model": "Qwen/Qwen2.5-1.5B",
                "training_type": "sft",
                "status": "training",
                "created_at": now,
            }
        )
        await tasks.create(
            {
                "id": "task-done",
                "name": "done",
                "dataset_id": "ds-1",
                "base_model": "Qwen/Qwen2.5-1.5B",
                "training_type": "sft",
                "status": "completed",
                "created_at": now,
            }
        )

    result = await recover_orphaned_runtime(sqlite_path)

    assert result["games"] == 2
    assert result["training_tasks"] == 1

    async with aiosqlite.connect(sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        games = GameRepository(db)
        assert (await games.get_by_id("game-running"))["status"] == "interrupted"
        assert (await games.get_by_id("game-paused"))["status"] == "interrupted"
        assert (await games.get_by_id("game-finished"))["status"] == "finished"
        tasks = TrainingTaskRepository(db)
        orphan = await tasks.get_by_id("task-training")
        assert orphan["status"] == "failed"
        assert "restart" in str(orphan.get("result")).lower()
        assert (await tasks.get_by_id("task-done"))["status"] == "completed"


async def test_recover_orphaned_runtime_is_noop_on_clean_db(sqlite_path: str) -> None:
    result = await recover_orphaned_runtime(sqlite_path)
    assert result == {"games": 0, "training_tasks": 0}
