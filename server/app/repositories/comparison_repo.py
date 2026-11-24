"""Append-only comparison snapshots; no foreign keys to mutable experiments."""

from __future__ import annotations

import builtins
import json
from typing import Any

import aiosqlite


class ComparisonRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(
        self, snapshot_id: str, title: str, created_at: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        await self.db.execute(
            "INSERT INTO comparison_snapshots (id, title, created_at, result) VALUES (?, ?, ?, ?)",
            (
                snapshot_id,
                title,
                created_at,
                json.dumps(result, ensure_ascii=False, allow_nan=False),
            ),
        )
        await self.db.commit()
        return await self.get(snapshot_id)

    async def get(self, snapshot_id: str) -> dict[str, Any]:
        async with self.db.execute(
            "SELECT id, title, created_at, result FROM comparison_snapshots WHERE id = ?",
            (snapshot_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        return {"id": row[0], "title": row[1], "created_at": row[2], "result": json.loads(row[3])}

    async def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.execute(
            "SELECT id, title, created_at FROM comparison_snapshots ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]

    async def for_source(
        self, game_id: str, created_at: str, limit: int, offset: int
    ) -> builtins.list[dict[str, Any]]:
        """Find saved cohort memberships, never infer scope from run ownership alone."""
        async with self.db.execute(
            """SELECT id, title, created_at, result FROM comparison_snapshots
            WHERE json_extract(result, '$.metric_version') = 'paired-cohort-v5'
              AND julianday(json_extract(result, '$.computed_at')) >= julianday(?)
              AND EXISTS (
                SELECT 1 FROM json_each(result, '$.coverage.members') member,
                  json_each(member.value, '$.game_ids') game
                WHERE game.value = ?
              )
            ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
            (created_at, game_id, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {"id": r[0], "title": r[1], "created_at": r[2], "result": json.loads(r[3])}
            for r in rows
        ]
