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

    async def get_by_player(
        self,
        player_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get traces for a specific player."""
        cursor = await self._db.execute(
            """
            SELECT * FROM traces WHERE player_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (player_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_trace(row) for row in rows]

    async def get_metrics(
        self,
        game_id: str | None = None,
        model: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregated metrics for traces with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if game_id:
            conditions.append("game_id = ?")
            params.append(game_id)
        if model:
            conditions.append("model = ?")
            params.append(model)
        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_cursor = await self._db.execute(
            f"SELECT COUNT(*) as total FROM traces {where_clause}",
            params,
        )
        count_row = await count_cursor.fetchone()

        metrics_cursor = await self._db.execute(
            f"""
            SELECT
                AVG(json_extract(metrics, '$.response_time_ms')) as avg_response_time,
                MIN(json_extract(metrics, '$.response_time_ms')) as min_response_time,
                MAX(json_extract(metrics, '$.response_time_ms')) as max_response_time,
                SUM(CASE WHEN json_extract(metrics, '$.used_langchain_parser') = 1
                    THEN 1 ELSE 0 END) as langchain_success
            FROM traces {where_clause}
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
        total = row["total"] if row else 0
        langchain_success = row["langchain_success"] if row else 0
        return {
            "version": version,
            "total_traces": total,
            "avg_response_time_ms": round(
                row["avg_response_time"] if row and row["avg_response_time"] else 0, 2
            ),
            "langchain_success_count": langchain_success,
            "success_rate": round(langchain_success / max(total, 1) * 100, 2),
        }


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
