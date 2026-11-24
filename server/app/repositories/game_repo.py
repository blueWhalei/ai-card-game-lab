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
        experiment_id: str | None = None,
        *,
        commit: bool = True,
    ) -> dict[str, Any]:
        """Insert a new game record and return it as a dict."""
        await self._db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, data_file, created_at, metadata, experiment_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                game_type,
                status,
                json.dumps(player_ids),
                data_file,
                created_at,
                json.dumps(metadata) if metadata else None,
                experiment_id,
            ),
        )
        if commit:
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

    async def get_many(self, game_ids: list[str]) -> list[dict[str, Any]]:
        """Load source metadata without exceeding SQLite's parameter limit."""
        rows: list[dict[str, Any]] = []
        ids = sorted(set(game_ids))
        for start in range(0, len(ids), 500):
            batch = ids[start : start + 500]
            placeholders = ",".join("?" for _ in batch)
            async with self._db.execute(
                f"SELECT * FROM games WHERE id IN ({placeholders})", batch
            ) as cursor:
                rows.extend(dict(row) for row in await cursor.fetchall())
        return rows

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
            f"SELECT COUNT(*) FROM games{where_clause}",
            params,
        )
        total = (await count_cursor.fetchone())[0]  # type: ignore[index]

        offset = (page - 1) * page_size
        data_cursor = await self._db.execute(
            f"SELECT * FROM games{where_clause} ORDER BY {col} {direction} LIMIT ? OFFSET ?",
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
        metadata_patch: dict[str, Any] | None = None,
    ) -> None:
        """Commit the terminal facts and all seat labels together."""
        try:
            await self._db.execute(
                """
                UPDATE games SET status = 'finished', winner_id = ?, winner_role = ?,
                    total_rounds = ?, finished_at = ?,
                    metadata = json_patch(COALESCE(metadata, '{}'), ?)
                WHERE id = ?
                """,
                (
                    winner_id,
                    winner_role,
                    total_rounds,
                    finished_at,
                    json.dumps(metadata_patch or {}),
                    game_id,
                ),
            )
            await self._db.execute(
                """
                UPDATE decision_points AS dp SET outcome = (
                    SELECT CASE won WHEN 1 THEN 'win' ELSE 'lose' END
                    FROM game_seat_results WHERE game_id = dp.game_id AND player_id = dp.player_id
                ) WHERE dp.game_id = ?
                """,
                (game_id,),
            )
            await self._db.commit()
        except BaseException:
            await self._db.rollback()
            raise

    async def list_by_experiment(self, experiment_id: str) -> list[dict[str, Any]]:
        """Return all games for an experiment (unordered)."""
        cursor = await self._db.execute(
            "SELECT * FROM games WHERE experiment_id = ?",
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
