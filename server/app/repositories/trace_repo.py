"""Trace and span data access layer (SQLite)."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite


class TraceRepository:
    """CRUD operations for the ``traces`` and ``spans`` tables."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create_trace(
        self,
        trace_id: str,
        game_id: str,
        round_number: int,
        player_id: str,
        model: str,
        prompt_version: str,
        input_snapshot: dict[str, Any],
        output_data: dict[str, Any],
        metrics: dict[str, Any],
        created_at: str,
    ) -> None:
        """Insert a new trace record."""
        await self._db.execute(
            """
            INSERT INTO traces (
                id, game_id, round_number, player_id, model, prompt_version,
                input_snapshot, output_data, metrics, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                game_id,
                round_number,
                player_id,
                model,
                prompt_version,
                json.dumps(input_snapshot, ensure_ascii=False),
                json.dumps(output_data, ensure_ascii=False),
                json.dumps(metrics, ensure_ascii=False),
                created_at,
            ),
        )
        await self._db.commit()

    async def create_span(
        self,
        span_id: str,
        trace_id: str,
        span_type: str,
        start_time: str,
        end_time: str | None,
        status: str,
        data: dict[str, Any] | None,
    ) -> None:
        """Insert a new span record."""
        await self._db.execute(
            """
            INSERT INTO spans (id, trace_id, span_type, start_time, end_time, status, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span_id,
                trace_id,
                span_type,
                start_time,
                end_time,
                status,
                json.dumps(data, ensure_ascii=False) if data else None,
            ),
        )
        await self._db.commit()

    async def get_by_game(self, game_id: str) -> list[dict[str, Any]]:
        """Get all traces for a game ordered by round_number."""
        cursor = await self._db.execute(
            """
            SELECT * FROM traces WHERE game_id = ? ORDER BY round_number, created_at
            """,
            (game_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_trace(row) for row in rows]

    async def get_by_id(self, trace_id: str) -> dict[str, Any] | None:
        """Get a single trace by ID."""
        cursor = await self._db.execute(
            "SELECT * FROM traces WHERE id = ?",
            (trace_id,),
        )
        row = await cursor.fetchone()
        return _row_to_trace(row) if row else None

    async def get_spans(self, trace_id: str) -> list[dict[str, Any]]:
        """Get all spans for a trace."""
        cursor = await self._db.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
            (trace_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_span(row) for row in rows]

    async def list_recent(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Return recent traces across all games."""
        items, _ = await self.list_filtered(limit=limit, offset=offset)
        return items

    async def get_by_experiment(
        self,
        experiment_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get traces for games belonging to an experiment."""
        items, _ = await self.list_filtered(
            experiment_id=experiment_id,
            limit=limit,
            offset=offset,
        )
        return items

    async def get_by_player(
        self,
        player_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get traces for a specific player."""
        items, _ = await self.list_filtered(
            player_id=player_id,
            limit=limit,
            offset=offset,
        )
        return items

    async def list_filtered(
        self,
        game_id: str | None = None,
        experiment_id: str | None = None,
        player_id: str | None = None,
        model: str | None = None,
        parser_ok: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List traces with AND-combined optional filters. Returns (items, total)."""
        from_sql, where_sql, params = _trace_filter_sql(
            game_id=game_id,
            experiment_id=experiment_id,
            player_id=player_id,
            model=model,
            parser_ok=parser_ok,
            table_alias="t",
        )
        count_cursor = await self._db.execute(
            f"SELECT COUNT(*) AS total {from_sql} {where_sql}",
            params,
        )
        count_row = await count_cursor.fetchone()
        total = int(count_row["total"] if count_row else 0)

        cursor = await self._db.execute(
            f"""
            SELECT t.* {from_sql}
            {where_sql}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        )
        rows = await cursor.fetchall()
        return [_row_to_trace(row) for row in rows], total

    async def get_metrics(
        self,
        game_id: str | None = None,
        experiment_id: str | None = None,
        player_id: str | None = None,
        model: str | None = None,
        parser_ok: bool | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregated metrics for traces with optional filters."""
        from_sql, where_sql, params = _trace_filter_sql(
            game_id=game_id,
            experiment_id=experiment_id,
            player_id=player_id,
            model=model,
            parser_ok=parser_ok,
            start_time=start_time,
            end_time=end_time,
            table_alias="t",
        )

        count_cursor = await self._db.execute(
            f"SELECT COUNT(*) as total {from_sql} {where_sql}",
            params,
        )
        count_row = await count_cursor.fetchone()

        metrics_cursor = await self._db.execute(
            f"""
            SELECT
                AVG(json_extract(t.metrics, '$.response_time_ms')) as avg_response_time,
                MIN(json_extract(t.metrics, '$.response_time_ms')) as min_response_time,
                MAX(json_extract(t.metrics, '$.response_time_ms')) as max_response_time,
                SUM(CASE WHEN json_extract(t.metrics, '$.used_langchain_parser') = 1
                    THEN 1 ELSE 0 END) as langchain_success
            {from_sql}
            {where_sql}
            """,
            params,
        )
        metrics_row = await metrics_cursor.fetchone()

        return {
            "total_traces": count_row["total"] if count_row else 0,
            "avg_response_time_ms": round(
                metrics_row["avg_response_time"] if metrics_row and metrics_row["avg_response_time"] else 0, 2
            ),
            "min_response_time_ms": round(
                metrics_row["min_response_time"] if metrics_row and metrics_row["min_response_time"] else 0, 2
            ),
            "max_response_time_ms": round(
                metrics_row["max_response_time"] if metrics_row and metrics_row["max_response_time"] else 0, 2
            ),
            "langchain_success_count": metrics_row["langchain_success"] if metrics_row else 0,
        }

    async def get_version_stats(self, version: str) -> dict[str, Any]:
        """Get aggregated stats for a single prompt version."""
        cursor = await self._db.execute(
            """
            SELECT
                COUNT(*) as total,
                AVG(json_extract(metrics, '$.response_time_ms')) as avg_response_time,
                SUM(CASE WHEN json_extract(metrics, '$.used_langchain_parser') = 1
                    THEN 1 ELSE 0 END) as langchain_success
            FROM traces WHERE prompt_version = ?
            """,
            (version,),
        )
        row = await cursor.fetchone()
        total = int(row["total"]) if row and row["total"] is not None else 0
        raw_success = row["langchain_success"] if row else None
        langchain_success = int(raw_success) if raw_success is not None else 0
        avg_raw = row["avg_response_time"] if row else None
        return {
            "version": version,
            "total_traces": total,
            "avg_response_time_ms": round(float(avg_raw) if avg_raw is not None else 0, 2),
            "langchain_success_count": langchain_success,
            "success_rate": round(langchain_success / max(total, 1) * 100, 2),
        }


def _trace_filter_sql(
    *,
    game_id: str | None = None,
    experiment_id: str | None = None,
    player_id: str | None = None,
    model: str | None = None,
    parser_ok: bool | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    table_alias: str = "t",
) -> tuple[str, str, list[Any]]:
    """Build FROM / WHERE fragments for optional trace filters.

    Returns ``(from_sql, where_sql, params)``. ``from_sql`` always starts with
    ``FROM traces {alias}`` and may join ``games`` when ``experiment_id`` is set.
    """
    a = table_alias
    from_sql = f"FROM traces {a}"
    conditions: list[str] = []
    params: list[Any] = []

    if experiment_id:
        from_sql += f" INNER JOIN games g ON g.id = {a}.game_id"
        conditions.append("g.experiment_id = ?")
        params.append(experiment_id)
    if game_id:
        conditions.append(f"{a}.game_id = ?")
        params.append(game_id)
    if player_id:
        conditions.append(f"{a}.player_id = ?")
        params.append(player_id)
    if model:
        conditions.append(f"{a}.model = ?")
        params.append(model)
    if parser_ok is True:
        conditions.append(
            f"json_extract({a}.metrics, '$.used_langchain_parser') = 1"
        )
    elif parser_ok is False:
        conditions.append(
            f"(json_extract({a}.metrics, '$.used_langchain_parser') IS NULL "
            f"OR json_extract({a}.metrics, '$.used_langchain_parser') = 0)"
        )
    if start_time:
        conditions.append(f"{a}.created_at >= ?")
        params.append(start_time)
    if end_time:
        conditions.append(f"{a}.created_at <= ?")
        params.append(end_time)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return from_sql, where_sql, params


def _row_to_trace(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert a traces row to a dictionary."""
    return {
        "id": row["id"],
        "game_id": row["game_id"],
        "round_number": row["round_number"],
        "player_id": row["player_id"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "input_snapshot": json.loads(row["input_snapshot"]) if row["input_snapshot"] else {},
        "output_data": json.loads(row["output_data"]) if row["output_data"] else {},
        "metrics": json.loads(row["metrics"]) if row["metrics"] else {},
        "created_at": row["created_at"],
    }


def _row_to_span(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert a spans row to a dictionary."""
    return {
        "id": row["id"],
        "trace_id": row["trace_id"],
        "span_type": row["span_type"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "status": row["status"],
        "data": json.loads(row["data"]) if row["data"] else {},
    }
