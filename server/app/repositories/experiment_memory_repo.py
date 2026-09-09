"""Per-experiment opponent notes for Policy memory."""

from __future__ import annotations

import aiosqlite


class ExperimentMemoryRepository:
    """CRUD for ``experiment_memory``."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get_notes(self, experiment_id: str, player_id: str) -> str:
        cursor = await self._db.execute(
            """
            SELECT notes FROM experiment_memory
            WHERE experiment_id = ? AND player_id = ?
            """,
            (experiment_id, player_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return ""
        return str(row["notes"] or "")

    async def upsert_notes(
        self,
        experiment_id: str,
        player_id: str,
        notes: str,
        updated_at: str,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO experiment_memory (experiment_id, player_id, notes, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(experiment_id, player_id) DO UPDATE SET
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (experiment_id, player_id, notes, updated_at),
        )
        await self._db.commit()

    async def clear_experiment(self, experiment_id: str) -> None:
        await self._db.execute(
            "DELETE FROM experiment_memory WHERE experiment_id = ?",
            (experiment_id,),
        )
        await self._db.commit()
