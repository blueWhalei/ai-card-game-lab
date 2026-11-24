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
        return int(await self._scalar(f"SELECT COUNT(*) FROM games{where}", params))

    async def total_rounds(self) -> int:
        frm, params = self._rounds_scope()
        return int(await self._scalar(f"SELECT COUNT(*) {frm}", params))

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
        return int(await self._scalar(f"SELECT SUM({col}) {frm}", params))

    async def total_prompt_tokens(self) -> int:
        col = "r.prompt_tokens" if self._experiment_id else "prompt_tokens"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        return int(await self._scalar(f"SELECT SUM({col}) {frm}", params))

    async def total_completion_tokens(self) -> int:
        col = "r.completion_tokens" if self._experiment_id else "completion_tokens"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        return int(await self._scalar(f"SELECT SUM({col}) {frm}", params))

    async def tokens_by_model(self) -> dict[str, int]:
        name_col = "r.model_name" if self._experiment_id else "model_name"
        token_col = "r.total_tokens" if self._experiment_id else "total_tokens"
        frm, params = self._rounds_scope(f"{token_col} IS NOT NULL AND {name_col} IS NOT NULL")
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
        return int(await self._scalar(f"SELECT COUNT(*) FROM games{where}", params))

    async def wins_by_role(self) -> dict[str, int]:
        where, params = self._games_clause("winner_role IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT winner_role, COUNT(*) as cnt FROM games{where} GROUP BY winner_role",
            params,
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def model_seat_rates(self) -> list[dict[str, Any]]:
        """Attribute a seat once, only when its rounds identify one model."""
        scope = "WHERE s.experiment_id = ?" if self._experiment_id else ""
        cursor = await self._db.execute(
            f"""
            WITH attributed AS (
                SELECT s.game_id, s.player_id, s.won, MIN(r.model_name) AS model
                FROM game_seat_results s JOIN rounds r
                  ON r.game_id = s.game_id AND r.player_id = s.player_id
                {scope}
                GROUP BY s.game_id, s.player_id
                HAVING COUNT(DISTINCT r.model_name) = 1 AND COUNT(r.model_name) = COUNT(*)
            )
            SELECT model, COUNT(*) AS seat_games, SUM(won) AS wins,
                   ROUND(AVG(won), 4) AS win_rate
            FROM attributed GROUP BY model ORDER BY win_rate DESC, model
            """,
            (self._experiment_id,) if self._experiment_id else (),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def response_time_percentiles(self) -> tuple[float, float]:
        """Return (p50_ms, p95_ms) from ordered response times."""
        col = "r.response_time_ms" if self._experiment_id else "response_time_ms"
        frm, params = self._rounds_scope(f"{col} IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT {col} {frm} ORDER BY {col}",
            params,
        )
        rows = list(await cursor.fetchall())
        if not rows:
            return 0.0, 0.0
        n = len(rows)
        p50_idx = min(int(n * 0.5), n - 1)
        p95_idx = min(int(n * 0.95), n - 1)
        return round(rows[p50_idx][0], 1), round(rows[p95_idx][0], 1)

    async def response_time_by_model(self) -> dict[str, float]:
        name_col = "r.model_name" if self._experiment_id else "model_name"
        ms_col = "r.response_time_ms" if self._experiment_id else "response_time_ms"
        frm, params = self._rounds_scope(f"{ms_col} IS NOT NULL AND {name_col} IS NOT NULL")
        cursor = await self._db.execute(
            f"SELECT {name_col}, AVG({ms_col}) as avg_ms {frm} GROUP BY {name_col}",
            params,
        )
        return {row[0]: round(row[1], 1) for row in await cursor.fetchall()}

    async def _scalar(self, sql: str, params: list[Any] | None = None) -> int | float:
        cursor = await self._db.execute(sql, params or [])
        row = await cursor.fetchone()
        value = row[0] if row else 0
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return float(value)
