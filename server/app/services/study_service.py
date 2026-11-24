"""Organize research without reimplementing experiments or analysis."""

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.study_operations_repo import (
    MAX_SAFE_INTEGER,
    TOKEN_FIELDS,
    StudyOperationsRepository,
)
from app.repositories.study_repo import StudyRepository
from app.schemas.study import CreateStudyRequest
from app.services.experiment_service import ExperimentService
from app.utils.exceptions import AppError
from app.utils.id_generator import generate_id


class StudyService:
    async def operations(
        self, db: aiosqlite.Connection, study_id: str, state: str, page: int
    ) -> dict[str, Any]:
        await db.execute("BEGIN")
        try:
            await self.get(db, study_id)
            repo = StudyOperationsRepository(db)
            rows, total = await repo.runs(study_id, state, page)
            usages = await repo.usage([row["id"] for row in rows])
            items = []
            for row in rows:
                recorded = usages.get(row["id"], {})
                n = recorded.get("trace_count", 0)
                fields = {}
                for field in TOKEN_FIELDS:
                    valid = recorded.get(f"{field}_count", 0)
                    missing = recorded.get(f"{field}_missing", 0)
                    value = recorded.get(f"{field}_sum", 0)
                    overflow = bool(valid and value > MAX_SAFE_INTEGER)
                    fields[field] = {
                        "value": int(value) if valid and not overflow else None,
                        "recorded_count": valid,
                        "missing_count": missing,
                        "invalid_count": n - valid - missing,
                        "overflow": overflow,
                    }
                items.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "target_games": row["target_games"],
                        "game_count": row["game_count"],
                        "states": {
                            key: row[key]
                            for key in (
                                "waiting",
                                "running",
                                "paused",
                                "finished",
                                "failed",
                                "interrupted",
                                "cancelled",
                                "unknown",
                            )
                        },
                        "no_bid_count": row["no_bid"],
                        "trace_count": n,
                        "usage": fields,
                    }
                )
            return {
                "study_id": study_id,
                "state": state,
                "page": page,
                "page_size": 20,
                "total": total,
                "items": items,
                "read_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await db.rollback()

    async def list(self, db: aiosqlite.Connection, limit: int, offset: int) -> list[dict[str, Any]]:
        return await StudyRepository(db).list_all(limit, offset)

    async def workspace(
        self,
        db: aiosqlite.Connection,
        study_id: str,
        experiments: ExperimentService,
    ) -> dict[str, Any]:
        study = await self.get(db, study_id)
        return {
            **study,
            "runs": await experiments.list_experiments(study_id=study_id),
            "comparisons": await StudyRepository(db).comparisons(study_id),
        }

    async def get(self, db: aiosqlite.Connection, study_id: str) -> dict[str, Any]:
        try:
            return await StudyRepository(db).get(study_id)
        except KeyError as exc:
            raise AppError("Research not found", "STUDY_NOT_FOUND", 404) from exc

    async def create(self, db: aiosqlite.Connection, body: CreateStudyRequest) -> dict[str, Any]:
        repo = StudyRepository(db)
        study_id = generate_id("study")
        await repo.create(study_id, body.title, body.question, datetime.now(UTC).isoformat())
        await db.commit()
        return await repo.get(study_id)

    async def attach(self, db: aiosqlite.Connection, study_id: str, experiment_id: str) -> None:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self.get(db, study_id)
            try:
                await ExperimentRepository(db).get_by_id(experiment_id)
            except KeyError as exc:
                raise AppError("Run not found", "EXPERIMENT_NOT_FOUND", 404) from exc
            repo = StudyRepository(db)
            owner = await repo.owner(experiment_id)
            if owner is not None and owner != study_id:
                raise AppError("Run already belongs to another research", "STUDY_RUN_CONFLICT", 409)
            if owner is None:
                await repo.attach(study_id, experiment_id, datetime.now(UTC).isoformat())
            await db.commit()
        except Exception:
            await db.rollback()
            raise
