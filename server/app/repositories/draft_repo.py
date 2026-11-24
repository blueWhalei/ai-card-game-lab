"""Persist drafts independently of browser origins and formal conclusions."""

import json

import aiosqlite

from app.schemas.draft import DraftKind, DraftRecord


class DraftRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def get(self, kind: DraftKind, object_id: str) -> DraftRecord | None:
        async with self.db.execute(
            "SELECT revision, updated_at, content FROM workspace_drafts WHERE kind=? AND object_id=?",
            (kind, object_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return DraftRecord(revision=row[0], updated_at=row[1], content=json.loads(row[2]))

    async def put(self, kind: DraftKind, object_id: str, record: DraftRecord) -> None:
        # Called under the service's IMMEDIATE transaction after checking revision.
        await self.db.execute(
            """INSERT INTO workspace_drafts (kind, object_id, revision, updated_at, content)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(kind, object_id) DO UPDATE SET
            revision=excluded.revision, updated_at=excluded.updated_at, content=excluded.content""",
            (kind, object_id, record.revision, record.updated_at, record.content.model_dump_json()),
        )
