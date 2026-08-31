"""Experiment (run) data access layer (SQLite)."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite


class ExperimentRepository:
    """CRUD operations for the ``experiments`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(
        self,
        experiment_id: str,
        name: str,
        notes: str,
        game_type: str,
        player_ids: list[str],
        target_games: int,
        created_at: str,
        updated_at: str,
    ) -> dict[str, Any]:
        await self._db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                name,
                notes,
                game_type,
                json.dumps(player_ids, ensure_ascii=False),
                target_games,
                created_at,
                updated_at,
            ),
        )
        await self._db.commit()
        return await self.get_by_id(experiment_id)

    async def get_by_id(self, experiment_id: str) -> dict[str, Any]:
        cursor = await self._db.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(experiment_id)
        return _row_to_dict(row)

    async def list_all(self) -> list[dict[str, Any]]:
        cursor = await self._db.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]

    async def touch_updated_at(self, experiment_id: str, updated_at: str) -> None:
        await self._db.execute(
            "UPDATE experiments SET updated_at = ? WHERE id = ?",
            (updated_at, experiment_id),
        )
        await self._db.commit()

    async def list_games(self, experiment_id: str) -> list[dict[str, Any]]:
        cursor = await self._db.execute(
            """
            SELECT * FROM games
            WHERE experiment_id = ?
            ORDER BY created_at DESC
            """,
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def count_train_usable_decisions(self, experiment_id: str) -> int:
        cursor = await self._db.execute(
            """
            SELECT COUNT(*) AS total
            FROM decision_points dp
            INNER JOIN games g ON g.id = dp.game_id
            WHERE g.experiment_id = ? AND dp.train_usable = 1
            """,
            (experiment_id,),
        )
        row = await cursor.fetchone()
        return int(row["total"] if row else 0)

    async def count_train_usable_by_player(self, experiment_id: str) -> dict[str, int]:
        """Count train_usable decision points per player within an experiment."""
        cursor = await self._db.execute(
            """
            SELECT dp.player_id AS player_id, COUNT(*) AS total
            FROM decision_points dp
            INNER JOIN games g ON g.id = dp.game_id
            WHERE g.experiment_id = ? AND dp.train_usable = 1
            GROUP BY dp.player_id
            """,
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        return {str(r["player_id"]): int(r["total"]) for r in rows}

    async def avg_response_ms_by_player(
        self,
        experiment_id: str,
    ) -> dict[str, tuple[float, int]]:
        """Average response_time_ms and trace count per player in an experiment."""
        cursor = await self._db.execute(
            """
            SELECT
                t.player_id AS player_id,
                AVG(json_extract(t.metrics, '$.response_time_ms')) AS avg_ms,
                COUNT(*) AS total
            FROM traces t
            INNER JOIN games g ON g.id = t.game_id
            WHERE g.experiment_id = ?
            GROUP BY t.player_id
            """,
            (experiment_id,),
        )
        rows = await cursor.fetchall()
        result: dict[str, tuple[float, int]] = {}
        for r in rows:
            avg_raw = r["avg_ms"]
            avg_ms = round(float(avg_raw), 2) if avg_raw is not None else 0.0
            result[str(r["player_id"])] = (avg_ms, int(r["total"]))
        return result

    async def compare_aggregates(self, experiment_id: str) -> dict[str, Any]:
        """Token, latency, decision, and parser totals for one experiment."""
        decision_cursor = await self._db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN dp.train_usable = 1 THEN 1 ELSE 0 END) AS usable
            FROM decision_points dp
            INNER JOIN games g ON g.id = dp.game_id
            WHERE g.experiment_id = ?
            """,
            (experiment_id,),
        )
        decision_row = await decision_cursor.fetchone()
        decision_count = int(decision_row["total"] if decision_row else 0)

        round_cursor = await self._db.execute(
            """
            SELECT
                AVG(r.response_time_ms) AS avg_ms,
                SUM(r.total_tokens) AS tokens,
                AVG(r.total_tokens) AS avg_tokens
            FROM rounds r
            INNER JOIN games g ON g.id = r.game_id
            WHERE g.experiment_id = ?
            """,
            (experiment_id,),
        )
        round_row = await round_cursor.fetchone()
        avg_ms_raw = round_row["avg_ms"] if round_row else None
        tokens_raw = round_row["tokens"] if round_row else None
        avg_tokens_raw = round_row["avg_tokens"] if round_row else None

        parser_cursor = await self._db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE WHEN json_extract(t.metrics, '$.used_langchain_parser') = 1
                    THEN 1 ELSE 0 END
                ) AS parser_ok
            FROM traces t
            INNER JOIN games g ON g.id = t.game_id
            WHERE g.experiment_id = ?
            """,
            (experiment_id,),
        )
        parser_row = await parser_cursor.fetchone()
        parser_n = int(parser_row["total"] if parser_row else 0)
        parser_ok = int(parser_row["parser_ok"] or 0) if parser_row else 0

        return {
            "decision_count": decision_count,
            "avg_response_time_ms": round(float(avg_ms_raw), 2) if avg_ms_raw is not None else 0.0,
            "total_tokens": int(tokens_raw) if tokens_raw is not None else 0,
            "avg_tokens_per_round": (
                round(float(avg_tokens_raw), 2) if avg_tokens_raw is not None else 0.0
            ),
            "parser_n": parser_n,
            "parser_ok": parser_ok,
        }


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    data = dict(row)
    raw_players = data.get("player_ids")
    if isinstance(raw_players, str):
        data["player_ids"] = json.loads(raw_players)
    return data
