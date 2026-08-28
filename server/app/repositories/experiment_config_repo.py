"""SQLite repository for experiment config profiles."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import aiosqlite


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_config(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "notes": row["notes"],
        "model_config": json.loads(row["model_config"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class ExperimentConfigRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def count(self) -> int:
        async with self._db.execute("SELECT COUNT(*) AS c FROM experiment_configs") as cursor:
            row = await cursor.fetchone()
            return int(row["c"] if row else 0)

    async def list_all(self) -> list[dict[str, Any]]:
        async with self._db.execute(
            "SELECT * FROM experiment_configs ORDER BY created_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_config(r) for r in rows]

    async def get(self, config_id: str) -> dict[str, Any] | None:
        async with self._db.execute(
            "SELECT * FROM experiment_configs WHERE id = ?",
            (config_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return _row_to_config(row) if row else None

    async def upsert(self, config: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        existing = await self.get(config["id"])
        created_at = existing["created_at"] if existing else now
        payload = {
            "id": config["id"],
            "name": config.get("name", config["id"]),
            "notes": config.get("notes", ""),
            "model_config": config.get(
                "model_config",
                {
                    "provider": "openai",
                    "model_name": "gpt-4o-mini",
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "max_tokens": 1024,
                },
            ),
            "created_at": created_at,
            "updated_at": now,
        }
        await self._db.execute(
            """
            INSERT INTO experiment_configs (id, name, notes, model_config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                notes = excluded.notes,
                model_config = excluded.model_config,
                updated_at = excluded.updated_at
            """,
            (
                payload["id"],
                payload["name"],
                payload["notes"],
                json.dumps(payload["model_config"], ensure_ascii=False),
                payload["created_at"],
                payload["updated_at"],
            ),
        )
        await self._db.commit()
        return deepcopy(payload)

    async def delete(self, config_id: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM experiment_configs WHERE id = ?",
            (config_id,),
        )
        await self._db.commit()
        return cursor.rowcount > 0
