"""Statistics data access layer (SQLite).

Provides read-only aggregate queries used by DataService.get_stats().
"""

from __future__ import annotations

from typing import Any

import aiosqlite


class StatsRepository:
    """Read-only aggregate queries over games and rounds tables."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def total_games(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM games")

    async def total_rounds(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM rounds")

    async def avg_response_time_ms(self) -> float | int:
        return await self._scalar(
            "SELECT AVG(response_time_ms) FROM rounds WHERE response_time_ms IS NOT NULL"
        )

    async def games_by_type(self) -> dict[str, int]:
        cursor = await self._db.execute(
            "SELECT game_type, COUNT(*) as cnt FROM games GROUP BY game_type"
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def models_usage(self) -> dict[str, int]:
        cursor = await self._db.execute(
            "SELECT model_name, COUNT(*) as cnt FROM rounds "
            "WHERE model_name IS NOT NULL GROUP BY model_name"
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def total_tokens(self) -> int:
        return await self._scalar(
            "SELECT SUM(total_tokens) FROM rounds WHERE total_tokens IS NOT NULL"
        )

    async def total_prompt_tokens(self) -> int:
        return await self._scalar(
            "SELECT SUM(prompt_tokens) FROM rounds WHERE prompt_tokens IS NOT NULL"
        )

    async def total_completion_tokens(self) -> int:
        return await self._scalar(
            "SELECT SUM(completion_tokens) FROM rounds WHERE completion_tokens IS NOT NULL"
        )

    async def tokens_by_model(self) -> dict[str, int]:
        cursor = await self._db.execute(
            "SELECT model_name, SUM(total_tokens) as total "
            "FROM rounds WHERE total_tokens IS NOT NULL AND model_name IS NOT NULL "
            "GROUP BY model_name"
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def avg_game_rounds(self) -> float | int:
        return await self._scalar(
            "SELECT AVG(total_rounds) FROM games WHERE total_rounds > 0"
        )

    async def games_with_winner(self) -> int:
        return await self._scalar(
            "SELECT COUNT(*) FROM games WHERE winner_id IS NOT NULL"
        )

    async def wins_by_role(self) -> dict[str, int]:
        cursor = await self._db.execute(
            "SELECT winner_role, COUNT(*) as cnt FROM games "
            "WHERE winner_role IS NOT NULL GROUP BY winner_role"
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def model_game_counts(self) -> dict[str, int]:
        cursor = await self._db.execute(
            "SELECT r.model_name, COUNT(DISTINCT r.game_id) as total_games "
            "FROM rounds r WHERE r.model_name IS NOT NULL "
            "GROUP BY r.model_name"
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def game_winner_rows(self) -> list[tuple[str, str, str]]:
        """Return (game_id, winner_id, player_ids) for games with a winner."""
        cursor = await self._db.execute(
            "SELECT id, winner_id, player_ids FROM games "
            "WHERE winner_id IS NOT NULL"
        )
        return [(row[0], row[1], row[2]) for row in await cursor.fetchall()]

    async def model_player_mapping(self) -> dict[str, dict[str, str]]:
        """Return {game_id: {player_id: model_name}} mapping."""
        cursor = await self._db.execute(
            "SELECT DISTINCT game_id, model_name, player_id FROM rounds "
            "WHERE model_name IS NOT NULL"
        )
        result: dict[str, dict[str, str]] = {}
        for row in await cursor.fetchall():
            gid, mname, pid = row[0], row[1], row[2]
            if gid not in result:
                result[gid] = {}
            result[gid][pid] = mname
        return result

    async def response_time_percentiles(self) -> tuple[float, float]:
        """Return (p50_ms, p95_ms) from ordered response times."""
        cursor = await self._db.execute(
            "SELECT response_time_ms FROM rounds "
            "WHERE response_time_ms IS NOT NULL ORDER BY response_time_ms"
        )
        rows = await cursor.fetchall()
        if not rows:
            return 0.0, 0.0
        n = len(rows)
        p50_idx = min(int(n * 0.5), n - 1)
        p95_idx = min(int(n * 0.95), n - 1)
        return round(rows[p50_idx][0], 1), round(rows[p95_idx][0], 1)

    async def response_time_by_model(self) -> dict[str, float]:
        cursor = await self._db.execute(
            "SELECT model_name, AVG(response_time_ms) as avg_ms "
            "FROM rounds WHERE response_time_ms IS NOT NULL AND model_name IS NOT NULL "
            "GROUP BY model_name"
        )
        return {row[0]: round(row[1], 1) for row in await cursor.fetchall()}

    async def _scalar(self, sql: str) -> Any:
        cursor = await self._db.execute(sql)
        row = await cursor.fetchone()
        return row[0] if row else 0
