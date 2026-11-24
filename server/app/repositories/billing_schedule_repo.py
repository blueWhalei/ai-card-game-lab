"""Durable schedule versions and next-run state; callers own transactions."""

from typing import Any

import aiosqlite


class BillingScheduleRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def current(self, study_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT s.*,r.next_due_at,r.last_attempt_id,r.consecutive_failures,r.error_code,"
            "r.updated_at FROM study_billing_schedule_revisions s "
            "JOIN study_billing_schedule_runtime r ON r.study_id=s.study_id AND r.schedule_revision=s.revision "
            "WHERE s.study_id=?",
            (study_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def history(self, study_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT s.*,c.organization_id,c.project_id,c.start_date FROM study_billing_schedule_revisions s "
            "JOIN study_billing_configs c ON c.study_id=s.study_id AND c.revision=s.config_revision "
            "WHERE s.study_id=? ORDER BY s.revision DESC LIMIT 10",
            (study_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def save(self, row: dict[str, Any]) -> None:
        await self.db.execute(
            """INSERT INTO study_billing_schedule_revisions
            (study_id,revision,config_revision,enabled,interval_minutes,reason,created_at)
            VALUES (:study_id,:revision,:config_revision,:enabled,:interval_minutes,:reason,:created_at)""",
            row,
        )
        await self.db.execute(
            """INSERT INTO study_billing_schedule_runtime
            (study_id,schedule_revision,next_due_at,consecutive_failures,updated_at)
            VALUES (:study_id,:revision,:next_due_at,0,:created_at)
            ON CONFLICT(study_id) DO UPDATE SET schedule_revision=excluded.schedule_revision,
            next_due_at=excluded.next_due_at,last_attempt_id=NULL,consecutive_failures=0,
            error_code=NULL,updated_at=excluded.updated_at""",
            row,
        )

    async def reserve(
        self, study_id: str, revision: int, due: str, now: str, attempt_id: str | None = None
    ) -> None:
        await self.db.execute(
            "UPDATE study_billing_schedule_runtime SET next_due_at=?,updated_at=?,"
            "last_attempt_id=COALESCE(?,last_attempt_id) WHERE study_id=? AND schedule_revision=?",
            (due, now, attempt_id, study_id, revision),
        )

    async def complete(
        self,
        study_id: str,
        revision: int,
        attempt_id: str,
        due: str | None,
        failures: int,
        error_code: str | None,
        now: str,
    ) -> None:
        await self.db.execute(
            "UPDATE study_billing_schedule_runtime SET next_due_at=?,consecutive_failures=?,"
            "error_code=?,updated_at=? WHERE study_id=? AND schedule_revision=? AND last_attempt_id=?",
            (due, failures, error_code, now, study_id, revision, attempt_id),
        )

    async def due(self, now: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT s.study_id,s.revision,s.config_revision FROM study_billing_schedule_revisions s "
            "JOIN study_billing_schedule_runtime r ON s.study_id=r.study_id AND s.revision=r.schedule_revision "
            "WHERE s.enabled=1 AND r.next_due_at<=? AND s.config_revision="
            "(SELECT MAX(c.revision) FROM study_billing_configs c WHERE c.study_id=s.study_id) "
            "ORDER BY r.next_due_at,s.study_id LIMIT 10",
            (now,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def heartbeat(self, now: str) -> None:
        await self.db.execute(
            "INSERT INTO billing_scheduler_heartbeat VALUES (1,?) "
            "ON CONFLICT(singleton) DO UPDATE SET checked_at=excluded.checked_at",
            (now,),
        )

    async def last_check(self) -> str | None:
        cursor = await self.db.execute(
            "SELECT checked_at FROM billing_scheduler_heartbeat WHERE singleton=1"
        )
        row = await cursor.fetchone()
        return str(row[0]) if row else None
