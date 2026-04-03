"""Game data access layer (SQLite)."""

import json
from typing import Any

import aiosqlite
import structlog

logger = structlog.get_logger()


class GameRepository:
    """CRUD operations for the ``games`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(
        self,
        game_id: str,
        game_type: str,
        player_ids: list[str],
        data_file: str,
        created_at: str,
        status: str = "created",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Insert a new game record and return it as a dict."""
        await self._db.execute(
            """
            INSERT INTO games (id, game_type, status, player_ids, data_file, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                game_type,
                status,
                json.dumps(player_ids),
                data_file,
                created_at,
                json.dumps(metadata) if metadata else None,
            ),
        )
        await self._db.commit()
        return await self.get_by_id(game_id)

    async def get_by_id(self, game_id: str) -> dict[str, Any]:
        """Fetch a single game by ID.

        Raises:
            KeyError: If the game does not exist.
        """
        cursor = await self._db.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(game_id)
        return dict(row)

    async def list_games(
        self,
        *,
        game_type: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a paginated, filtered list of games and the total count."""
        conditions: list[str] = []
        params: list[Any] = []

        if game_type:
            conditions.append("game_type = ?")
            params.append(game_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to)

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        allowed_sort = {"created_at", "game_type", "status", "total_rounds"}
        col = sort_by if sort_by in allowed_sort else "created_at"
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        count_cursor = await self._db.execute(
            f"SELECT COUNT(*) FROM games{where_clause}",  # noqa: S608
            params,
        )
        total = (await count_cursor.fetchone())[0]  # type: ignore[index]

        offset = (page - 1) * page_size
        data_cursor = await self._db.execute(
            f"SELECT * FROM games{where_clause} ORDER BY {col} {direction} LIMIT ? OFFSET ?",  # noqa: S608
            [*params, page_size, offset],
        )
        rows = await data_cursor.fetchall()
        return [dict(r) for r in rows], total

    async def update_status(self, game_id: str, status: str) -> None:
        """Update the status of a game."""
        await self._db.execute(
            "UPDATE games SET status = ? WHERE id = ?",
            (status, game_id),
        )
        await self._db.commit()

    async def update_result(
        self,
        game_id: str,
        *,
        winner_id: str | None,
        winner_role: str | None,
        total_rounds: int,
        finished_at: str,
    ) -> None:
        """Update a game with its final result."""
        await self._db.execute(
            """
            UPDATE games
            SET status = 'finished', winner_id = ?, winner_role = ?,
                total_rounds = ?, finished_at = ?
            WHERE id = ?
            """,
            (winner_id, winner_role, total_rounds, finished_at, game_id),
        )
        await self._db.commit()
