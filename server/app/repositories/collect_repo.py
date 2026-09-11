"""Durable collection reservations; caller owns the transaction."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite


class CollectRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get(self, experiment_id: str, key: str) -> dict[str, Any] | None:
        cursor = await self._db.execute(
            "SELECT requested_count, game_ids FROM experiment_collect_requests "
            "WHERE experiment_id = ? AND request_key = ?",
            (experiment_id, key),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {"requested_count": int(row[0]), "game_ids": json.loads(row[1])}

    async def next_index(self, experiment_id: str) -> int:
        cursor = await self._db.execute(
            "SELECT COALESCE(MAX(start_index + game_count), 0) "
            "FROM experiment_collect_requests WHERE experiment_id = ?",
            (experiment_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def create(
        self,
        experiment_id: str,
        key: str,
        requested_count: int,
        start_index: int,
        game_ids: list[str],
        created_at: str,
    ) -> None:
        await self._db.execute(
            "INSERT INTO experiment_collect_requests "
            "(experiment_id, request_key, requested_count, start_index, game_count, game_ids, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                experiment_id,
                key,
                requested_count,
                start_index,
                len(game_ids),
                json.dumps(game_ids),
                created_at,
            ),
        )
