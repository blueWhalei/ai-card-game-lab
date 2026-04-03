"""Dataset metadata access layer (SQLite)."""

import json
from typing import Any

import aiosqlite


class DatasetRepository:
    """CRUD operations for the ``datasets`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a dataset record and return it as a dict."""
        await self._db.execute(
            """
            INSERT INTO datasets (id, name, game_type, filters, sample_count, file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["name"],
                data["game_type"],
                json.dumps(data["filters"], ensure_ascii=False),
                data["sample_count"],
                data["file_path"],
                data["created_at"],
            ),
        )
        await self._db.commit()
        return await self.get_by_id(data["id"])

    async def get_by_id(self, dataset_id: str) -> dict[str, Any]:
        """Fetch a single dataset by ID.

        Raises:
            KeyError: If the dataset does not exist.
        """
        cursor = await self._db.execute(
            "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(dataset_id)
        return self._normalize(dict(row))

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all datasets ordered by creation time descending."""
        cursor = await self._db.execute(
            "SELECT * FROM datasets ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [self._normalize(dict(r)) for r in rows]

    async def delete(self, dataset_id: str) -> None:
        """Delete a dataset by ID.

        Raises:
            KeyError: If the dataset does not exist.
        """
        cursor = await self._db.execute(
            "SELECT id FROM datasets WHERE id = ?", (dataset_id,)
        )
        if await cursor.fetchone() is None:
            raise KeyError(dataset_id)
        await self._db.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        await self._db.commit()

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON string fields back to Python objects."""
        if isinstance(row.get("filters"), str):
            row["filters"] = json.loads(row["filters"])
        return row
