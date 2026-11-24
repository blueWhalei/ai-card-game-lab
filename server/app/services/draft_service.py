"""Workspace draft persistence with optimistic concurrency across windows."""

from datetime import UTC, datetime

import aiosqlite

from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.draft_repo import DraftRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.research_repo import ResearchRepository
from app.schemas.draft import (
    ComparisonDraft,
    DraftKind,
    DraftRecord,
    NotebookDraft,
    SaveDraftRequest,
)


class DraftConflictError(Exception):
    """Another editor saved a newer draft; the caller must preserve local text."""


class DraftService:
    async def read(self, db: aiosqlite.Connection, kind: DraftKind, object_id: str) -> DraftRecord:
        if kind == "experiment":
            source = await ExperimentRepository(db).get_by_id(object_id)
            initial: NotebookDraft | ComparisonDraft = NotebookDraft(
                kind=kind,
                hypothesis=source["hypothesis"],
                notes=source["notes"],
                conclusion=source["conclusion"],
                tags_input=", ".join(source["tags"]),
            )
        else:
            await ComparisonRepository(db).get(object_id)
            initial = ComparisonDraft(
                kind=kind,
                expected_revision=await ResearchRepository(db).latest(object_id),
                observations="",
                interpretation="",
                limitations="",
                evidence=[],
            )
        saved = await DraftRepository(db).get(kind, object_id)
        return saved or DraftRecord(revision=0, updated_at=None, content=initial)

    async def save(
        self,
        db: aiosqlite.Connection,
        kind: DraftKind,
        object_id: str,
        request: SaveDraftRequest,
    ) -> DraftRecord:
        if request.content.kind != kind:
            raise ValueError("Draft content does not match its scope")
        await db.execute("BEGIN IMMEDIATE")
        try:
            current = await self.read(db, kind, object_id)
            if request.expected_revision != current.revision:
                raise DraftConflictError("A newer draft exists in another window")
            record = DraftRecord(
                revision=current.revision + 1,
                updated_at=datetime.now(UTC).isoformat(),
                content=request.content,
            )
            await DraftRepository(db).put(kind, object_id, record)
            await db.commit()
            return record
        except Exception:
            await db.rollback()
            raise
