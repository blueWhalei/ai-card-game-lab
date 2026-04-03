"""Player statistics data access layer (SQLite).

Provides read-only queries for AI player statistics.
"""

from __future__ import annotations

import re
from typing import Any

import aiosqlite

# Characters with special meaning in SQL LIKE patterns
_LIKE_ESCAPE_RE = re.compile(r"([%_\\])")


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters in a value."""
    return _LIKE_ESCAPE_RE.sub(r"\\\1", value)


class PlayerStatsRepository:
    """Read-only queries for AI player statistics."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get_all_player_ids(self) -> list[str]:
        """Get distinct player IDs from the games table."""
        cursor = await self._db.execute(
            """
            SELECT DISTINCT json_each.value as player_id
            FROM games, json_each(player_ids)
            WHERE json_valid(player_ids)
            """,
        )
        rows = await cursor.fetchall()
        return [row["player_id"] for row in rows]

    async def count_games_played(self, player_id: str) -> int:
        """Count finished games for a player."""
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM games WHERE player_ids LIKE ? AND status = 'finished'",
            [f'%"{_escape_like(player_id)}"%'],
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def count_wins(self, player_id: str) -> int:
        """Count games won by a player."""
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM games WHERE winner_id = ?",
            [player_id],
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_last_game(self, player_id: str) -> dict[str, Any] | None:
        """Get the most recent finished game for a player."""
        cursor = await self._db.execute(
            """
            SELECT id, created_at FROM games
            WHERE player_ids LIKE ? AND status = 'finished'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [f'%"{_escape_like(player_id)}"%'],
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {"id": row["id"], "created_at": row["created_at"]}
