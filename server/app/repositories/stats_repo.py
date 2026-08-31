"""Statistics data access layer (SQLite).

Provides read-only aggregate queries used by DataService.get_stats().
"""

from __future__ import annotations

from typing import Any

import aiosqlite


class StatsRepository:
    """Read-only aggregate queries over games and rounds tables."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        *,
        experiment_id: str | None = None,
    ) -> None:
        self._db = db
        self._experiment_id = experiment_id

    def _games_clause(self, extra: str | None = None) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if self._experiment_id:
            clauses.append("experiment_id = ?")
            params.append(self._experiment_id)
        if extra:
            clauses.append(extra)
        if not clauses:
            return "", []
        return " WHERE " + " AND ".join(clauses), params

    def _rounds_scope(self, extra: str | None = None) -> tuple[str, list[Any]]:
        if self._experiment_id:
            clauses = ["g.experiment_id = ?"]
            params: list[Any] = [self._experiment_id]
            if extra:
                clauses.append(extra)
            where = " WHERE " + " AND ".join(clauses)
            return (
                f"FROM rounds r INNER JOIN games g ON g.id = r.game_id{where}",
                params,
            )
        extra_sql = f" WHERE {extra}" if extra else ""
        return f"FROM rounds{extra_sql}", []

    async def total_games(self) -> int:
        where, params = self._games_clause()
        return await self._scalar(f"SELECT COUNT(*) FROM games{where}", params)

    async def total_rounds(self) -> int:
        frm, params = self._rounds_scope()
        return await self._scalar(f"SELECT COUNT(*) {frm}", params)

    async def avg_response_time_ms(self) -> float | int:
        col = "r.response_time_ms" if self._experiment_id else "response_time_ms"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        return await self._scalar(f"SELECT AVG({col}) {frm}", params)

    async def games_by_type(self) -> dict[str, int]:
        where, params = self._games_clause()
        cursor = await self._db.execute(
            f"SELECT game_type, COUNT(*) as cnt FROM games{where} GROUP BY game_type",
            params,
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def models_usage(self) -> dict[str, int]:
        col = "r.model_name" if self._experiment_id else "model_name"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT {col}, COUNT(*) as cnt {frm} GROUP BY {col}",
            params,
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def total_tokens(self) -> int:
        col = "r.total_tokens" if self._experiment_id else "total_tokens"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        return await self._scalar(f"SELECT SUM({col}) {frm}", params)

    async def total_prompt_tokens(self) -> int:
        col = "r.prompt_tokens" if self._experiment_id else "prompt_tokens"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        return await self._scalar(f"SELECT SUM({col}) {frm}", params)

    async def total_completion_tokens(self) -> int:
        col = "r.completion_tokens" if self._experiment_id else "completion_tokens"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        return await self._scalar(f"SELECT SUM({col}) {frm}", params)

    async def tokens_by_model(self) -> dict[str, int]:
        name_col = "r.model_name" if self._experiment_id else "model_name"
        token_col = "r.total_tokens" if self._experiment_id else "total_tokens"
        frm, params = self._rounds_scope(
            f"{token_col} IS NOT NULL AND {name_col} IS NOT NULL"
        )
        cursor = await self._db.execute(
            f"SELECT {name_col}, SUM({token_col}) as total {frm} GROUP BY {name_col}",
            params,
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def avg_game_rounds(self) -> float | int:
        where, params = self._games_clause("total_rounds > 0")
        return await self._scalar(f"SELECT AVG(total_rounds) FROM games{where}", params)

    async def games_with_winner(self) -> int:
        where, params = self._games_clause("winner_id IS NOT NULL")
        return await self._scalar(f"SELECT COUNT(*) FROM games{where}", params)

    async def wins_by_role(self) -> dict[str, int]:
        where, params = self._games_clause("winner_role IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT winner_role, COUNT(*) as cnt FROM games{where} GROUP BY winner_role",
            params,
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def model_game_counts(self) -> dict[str, int]:
        if self._experiment_id:
            frm, params = self._rounds_scope("r.model_name IS NOT NULL")
            sql = (
                f"SELECT r.model_name, COUNT(DISTINCT r.game_id) as total_games {frm} "
                "GROUP BY r.model_name"
            )
        else:
            sql = (
                "SELECT r.model_name, COUNT(DISTINCT r.game_id) as total_games "
                "FROM rounds r WHERE r.model_name IS NOT NULL GROUP BY r.model_name"
            )
            params = []
        cursor = await self._db.execute(sql, params)
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def game_winner_rows(self) -> list[tuple[str, str, str]]:
        """Return (game_id, winner_id, player_ids) for games with a winner."""
        where, params = self._games_clause("winner_id IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT id, winner_id, player_ids FROM games{where}",
            params,
        )
        return [(row[0], row[1], row[2]) for row in await cursor.fetchall()]

    async def model_player_mapping(self) -> dict[str, dict[str, str]]:
        """Return {game_id: {player_id: model_name}} mapping."""
        gid = "r.game_id" if self._experiment_id else "game_id"
        mname = "r.model_name" if self._experiment_id else "model_name"
        pid = "r.player_id" if self._experiment_id else "player_id"
        frm, params = self._rounds_scope(f"{mname} IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT DISTINCT {gid}, {mname}, {pid} {frm}",
            params,
        )
        result: dict[str, dict[str, str]] = {}
        for row in await cursor.fetchall():
            game_id, model_name, player_id = row[0], row[1], row[2]
            if game_id not in result:
                result[game_id] = {}
            result[game_id][player_id] = model_name
        return result

    async def response_time_percentiles(self) -> tuple[float, float]:
        """Return (p50_ms, p95_ms) from ordered response times."""
        col = "r.response_time_ms" if self._experiment_id else "response_time_ms"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT {col} {frm} ORDER BY {col}",
            params,
        )
        rows = await cursor.fetchall()
        if not rows:
            return 0.0, 0.0
        n = len(rows)
        p50_idx = min(int(n * 0.5), n - 1)
        p95_idx = min(int(n * 0.95), n - 1)
        return round(rows[p50_idx][0], 1), round(rows[p95_idx][0], 1)

    async def response_time_by_model(self) -> dict[str, float]:
        name_col = "r.model_name" if self._experiment_id else "model_name"
        ms_col = "r.response_time_ms" if self._experiment_id else "response_time_ms"
        frm, params = self._rounds_scope(
            f"{ms_col} IS NOT NULL AND {name_col} IS NOT NULL"
        )
        cursor = await self._db.execute(
            f"SELECT {name_col}, AVG({ms_col}) as avg_ms {frm} GROUP BY {name_col}",
            params,
        )
        return {row[0]: round(row[1], 1) for row in await cursor.fetchall()}

    async def _scalar(self, sql: str, params: list[Any] | None = None) -> Any:
        cursor = await self._db.execute(sql, params or [])
        row = await cursor.fetchone()
        return row[0] if row else 0
