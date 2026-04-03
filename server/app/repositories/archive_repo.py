"""Archive data access layer (SQLite).

Provides queries used by ArchiveService for archiving and cleanup.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import aiosqlite


class ArchiveRepository:
    """Read and delete operations for game archiving."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def count_games(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM games")

    async def count_rounds(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM rounds")

    async def count_traces(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM traces")

    async def count_decisions(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM decision_points")

    async def count_old_games(self, days: int) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        return await self._scalar(
            "SELECT COUNT(*) FROM games WHERE created_at < ?", [cutoff]
        )

    async def fetch_old_games(
        self,
        cutoff: str,
        game_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if game_type:
            cursor = await self._db.execute(
                "SELECT * FROM games WHERE created_at < ? AND game_type = ?",
                [cutoff, game_type],
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM games WHERE created_at < ?",
                [cutoff],
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def fetch_rounds_for_games(self, game_ids: list[str]) -> list[dict[str, Any]]:
        if not game_ids:
            return []
        placeholders = ",".join("?" * len(game_ids))
        cursor = await self._db.execute(
            f"SELECT * FROM rounds WHERE game_id IN ({placeholders})",
            game_ids,
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def fetch_traces_for_games(self, game_ids: list[str]) -> list[dict[str, Any]]:
        if not game_ids:
            return []
        placeholders = ",".join("?" * len(game_ids))
        cursor = await self._db.execute(
            f"SELECT * FROM traces WHERE game_id IN ({placeholders})",
            game_ids,
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def fetch_decisions_for_games(self, game_ids: list[str]) -> list[dict[str, Any]]:
        if not game_ids:
            return []
        placeholders = ",".join("?" * len(game_ids))
        cursor = await self._db.execute(
            f"SELECT * FROM decision_points WHERE game_id IN ({placeholders})",
            game_ids,
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def count_rounds_for_games(self, game_ids: list[str]) -> int:
        if not game_ids:
            return 0
        placeholders = ",".join("?" * len(game_ids))
        return await self._scalar(
            f"SELECT COUNT(*) FROM rounds WHERE game_id IN ({placeholders})", game_ids
        )

    async def count_traces_for_games(self, game_ids: list[str]) -> int:
        if not game_ids:
            return 0
        placeholders = ",".join("?" * len(game_ids))
        return await self._scalar(
            f"SELECT COUNT(*) FROM traces WHERE game_id IN ({placeholders})", game_ids
        )

    async def count_decisions_for_games(self, game_ids: list[str]) -> int:
        if not game_ids:
            return 0
        placeholders = ",".join("?" * len(game_ids))
        return await self._scalar(
            f"SELECT COUNT(*) FROM decision_points WHERE game_id IN ({placeholders})",
            game_ids,
        )

    async def delete_by_game_ids(self, game_ids: list[str]) -> None:
        """Delete all data for the given game IDs (spans, traces, decisions, rounds, games)."""
        if not game_ids:
            return
        placeholders = ",".join("?" * len(game_ids))

        await self._db.execute(
            f"DELETE FROM spans WHERE trace_id IN "
            f"(SELECT id FROM traces WHERE game_id IN ({placeholders}))",
            game_ids,
        )
        await self._db.execute(f"DELETE FROM traces WHERE game_id IN ({placeholders})", game_ids)
        await self._db.execute(
            f"DELETE FROM decision_points WHERE game_id IN ({placeholders})", game_ids
        )
        await self._db.execute(f"DELETE FROM rounds WHERE game_id IN ({placeholders})", game_ids)
        await self._db.execute(f"DELETE FROM games WHERE id IN ({placeholders})", game_ids)
        await self._db.commit()

    async def _scalar(self, sql: str, params: list[Any] | None = None) -> Any:
        cursor = await self._db.execute(sql, params or [])
        row = await cursor.fetchone()
        return row[0] if row else 0
