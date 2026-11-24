"""Versioned configuration and immutable successful supplier cost snapshots."""

from typing import Any

import aiosqlite


class StudyBillingRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def config(self, study_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT * FROM study_billing_configs WHERE study_id=? ORDER BY revision DESC LIMIT 1",
            (study_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_config(self, row: dict[str, Any]) -> None:
        await self.db.execute(
            """INSERT INTO study_billing_configs
            (study_id,revision,organization_id,project_id,start_date,limit_amount,
             enforcement_enabled,max_age_hours,reason,created_at)
            VALUES (:study_id,:revision,:organization_id,:project_id,:start_date,:limit_amount,
                    :enforcement_enabled,:max_age_hours,:reason,:created_at)""",
            row,
        )

    async def config_history(self, study_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM study_billing_configs WHERE study_id=? ORDER BY revision DESC LIMIT 10",
            (study_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def attempts(self, study_id: str, revision: int | None = None) -> list[dict[str, Any]]:
        clause = " AND a.revision=?" if revision is not None else ""
        params = (study_id, revision) if revision is not None else (study_id,)
        cursor = await self.db.execute(
            "SELECT a.id,a.study_id,a.revision,a.status,a.start_time,a.end_time,a.started_at,"
            "a.finished_at,a.error_code,a.amount,a.trigger,a.schedule_revision,c.organization_id,c.project_id,c.start_date,"
            "c.limit_amount,c.enforcement_enabled,c.max_age_hours,c.reason "
            "FROM study_billing_attempts a JOIN study_billing_configs c "
            "ON a.study_id=c.study_id AND a.revision=c.revision WHERE a.study_id=?"
            + clause
            + " ORDER BY a.started_at DESC,a.id DESC LIMIT 10",
            params,
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def latest_success(self, study_id: str, revision: int) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT id,start_time,end_time,finished_at,amount FROM study_billing_attempts "
            "WHERE study_id=? AND revision=? AND status='succeeded' "
            "ORDER BY started_at DESC,id DESC LIMIT 1",
            (study_id, revision),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def attempt(self, study_id: str, attempt_id: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT a.*,c.organization_id,c.project_id,c.start_date,c.limit_amount,"
            "c.enforcement_enabled,c.max_age_hours,c.reason FROM study_billing_attempts a "
            "JOIN study_billing_configs c ON a.study_id=c.study_id AND a.revision=c.revision "
            "WHERE a.study_id=? AND a.id=?",
            (study_id, attempt_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def begin_attempt(self, row: dict[str, Any]) -> None:
        await self.db.execute(
            """INSERT INTO study_billing_attempts
            (id,study_id,revision,status,start_time,end_time,started_at,trigger,schedule_revision)
            VALUES (:id,:study_id,:revision,'running',:start_time,:end_time,:started_at,:trigger,:schedule_revision)""",
            {
                **row,
                "trigger": row.get("trigger", "manual"),
                "schedule_revision": row.get("schedule_revision"),
            },
        )

    async def finish(
        self,
        attempt_id: str,
        status: str,
        finished_at: str,
        error_code: str | None = None,
        amount: str | None = None,
        items_json: str | None = None,
    ) -> bool:
        cursor = await self.db.execute(
            "UPDATE study_billing_attempts SET status=?,finished_at=?,error_code=?,"
            "amount=?,items_json=? WHERE id=? AND status='running'",
            (status, finished_at, error_code, amount, items_json, attempt_id),
        )
        return cursor.rowcount == 1
