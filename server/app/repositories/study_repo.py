"""Research organization only; experiment and conclusion data remain at their source."""

from __future__ import annotations

from typing import Any

import aiosqlite


class StudyRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(self, study_id: str, title: str, question: str, now: str) -> None:
        await self.db.execute(
            "INSERT INTO studies (id,title,question,created_at,updated_at) VALUES (?,?,?,?,?)",
            (study_id, title, question, now, now),
        )

    async def get(self, study_id: str) -> dict[str, Any]:
        cursor = await self.db.execute("SELECT * FROM studies WHERE id=?", (study_id,))
        row = await cursor.fetchone()
        if row is None:
            raise KeyError(study_id)
        return dict(row)

    async def list_all(self, limit: int, offset: int) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            """
            SELECT s.*,
              (SELECT COUNT(*) FROM study_runs r WHERE r.study_id=s.id) AS run_count,
              MAX(s.updated_at, COALESCE((SELECT MAX(e.updated_at) FROM experiments e
                JOIN study_runs r ON r.experiment_id=e.id WHERE r.study_id=s.id), ''))
                AS last_activity_at
            FROM studies s ORDER BY last_activity_at DESC, s.id DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def owner(self, experiment_id: str) -> str | None:
        cursor = await self.db.execute(
            "SELECT study_id FROM study_runs WHERE experiment_id=?", (experiment_id,)
        )
        row = await cursor.fetchone()
        return str(row[0]) if row else None

    async def attach(self, study_id: str, experiment_id: str, now: str) -> None:
        await self.db.execute(
            "INSERT INTO study_runs (study_id,experiment_id) VALUES (?,?)",
            (study_id, experiment_id),
        )
        await self.db.execute("UPDATE studies SET updated_at=? WHERE id=?", (now, study_id))

    async def comparisons(self, study_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            """
            SELECT c.id,c.title,c.created_at,
              (SELECT COUNT(*) FROM research_revisions v WHERE v.comparison_id=c.id)
                AS revision_count
            FROM comparison_snapshots c
            WHERE json_array_length(c.result, '$.experiments') >= 2
              AND NOT EXISTS (
                SELECT 1 FROM json_each(c.result, '$.experiments') member
                WHERE NOT EXISTS (SELECT 1 FROM study_runs r
                  WHERE r.study_id=? AND r.experiment_id=json_extract(member.value, '$.id'))
              )
            ORDER BY c.created_at DESC, c.id DESC
            """,
            (study_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
