"""Mark in-flight work as interrupted after a process restart."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.database import open_db_connection
from app.repositories.game_repo import GameRepository
from app.repositories.training_repo import TrainingTaskRepository

if TYPE_CHECKING:
    import aiosqlite

logger = structlog.get_logger()

ORPHAN_GAME_STATUSES: tuple[str, ...] = ("running", "paused")
ORPHAN_TRAINING_STATUSES: tuple[str, ...] = ("pending", "exporting", "training")
_RESTART_REASON = "Process restarted before the task completed"


async def recover_orphaned_runtime(sqlite_path: str) -> dict[str, int]:
    """Close out games/training tasks that cannot survive a process restart."""
    db = await open_db_connection(sqlite_path)
    try:
        games_closed = await _recover_games(db)
        tasks_closed = await _recover_training_tasks(db)
    finally:
        await db.close()

    if games_closed or tasks_closed:
        logger.warning(
            "orphaned_runtime_recovered",
            games=games_closed,
            training_tasks=tasks_closed,
        )
    return {"games": games_closed, "training_tasks": tasks_closed}


async def _recover_games(db: aiosqlite.Connection) -> int:
    repo = GameRepository(db)
    closed = 0
    for status in ORPHAN_GAME_STATUSES:
        rows, _ = await repo.list_games(status=status, page=1, page_size=1000)
        for row in rows:
            await repo.update_status(str(row["id"]), "interrupted")
            closed += 1
    return closed


async def _recover_training_tasks(db: aiosqlite.Connection) -> int:
    repo = TrainingTaskRepository(db)
    now = datetime.now(tz=UTC).isoformat()
    closed = 0
    for status in ORPHAN_TRAINING_STATUSES:
        rows, _ = await repo.list_all(status=status, page=1, page_size=1000)
        for row in rows:
            result: dict[str, Any] = {"error": _RESTART_REASON}
            existing = row.get("result")
            if isinstance(existing, dict):
                result = {**existing, **result}
            await repo.update_status(
                str(row["id"]),
                "failed",
                result=result,
                finished_at=now,
            )
            closed += 1
    return closed
