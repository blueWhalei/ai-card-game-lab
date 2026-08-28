"""Experiment config statistics data access layer (SQLite).

Provides read-only queries for experiment config statistics.
"""

from __future__ import annotations

from typing import Any

import aiosqlite


class ExperimentConfigStatsRepository:
    """Read-only queries for experiment config statistics."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def count_games_played(self, config_id: str) -> int:
        """Count finished games for an experiment config."""
        cursor = await self._db.execute(
            """
            SELECT COUNT(DISTINCT g.id) FROM games g, json_each(g.player_ids) AS je
            WHERE json_valid(g.player_ids)
              AND je.value = ?
              AND g.status = 'finished'
            """,
            [config_id],
        )
        row = await cursor.fetchone()
        return int(row[0] if row else 0)

    async def count_wins(self, config_id: str) -> int:
        """Count games won by an experiment config."""
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM games WHERE winner_id = ?",
            [config_id],
        )
        row = await cursor.fetchone()
        return int(row[0] if row else 0)

    async def get_last_game(self, config_id: str) -> dict[str, Any] | None:
        """Get the most recent finished game for an experiment config."""
        cursor = await self._db.execute(
            """
            SELECT g.id, g.created_at FROM games g, json_each(g.player_ids) AS je
            WHERE json_valid(g.player_ids)
              AND je.value = ?
              AND g.status = 'finished'
            ORDER BY g.created_at DESC
            LIMIT 1
            """,
            [config_id],
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {"id": row["id"], "created_at": row["created_at"]}
