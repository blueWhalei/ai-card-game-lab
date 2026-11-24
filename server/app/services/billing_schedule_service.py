"""Opt-in scheduling does not weaken cost admission checks or expand cost coverage."""

from datetime import UTC, datetime, timedelta
from typing import Any

import aiosqlite

from app.config import Settings
from app.repositories.billing_schedule_repo import BillingScheduleRepository
from app.repositories.study_billing_repo import StudyBillingRepository
from app.repositories.study_repo import StudyRepository
from app.schemas.study_billing import BillingScheduleRequest
from app.services.openai_costs import billing_error
from app.utils.exceptions import AppError


async def finish_scheduled_attempt(
    db: aiosqlite.Connection, attempt: dict[str, Any], error_code: str | None, now: datetime
) -> None:
    """Called inside the same transaction that finalizes a sync attempt."""
    if attempt.get("schedule_revision") is None:
        return
    repo = BillingScheduleRepository(db)
    plan = await repo.current(attempt["study_id"])
    if not plan or plan["revision"] != attempt["schedule_revision"] or not plan["enabled"]:
        return
    failures = plan["consecutive_failures"] + 1 if error_code else 0
    delay = min(plan["interval_minutes"] * (2 ** min(failures, 6)), 1440)
    retryable = error_code in (
        None,
        "BILLING_NETWORK",
        "BILLING_RATE_LIMIT",
        "BILLING_REMOTE",
        "BILLING_INTERRUPTED",
    )
    due = (now + timedelta(minutes=delay)).isoformat() if retryable else None
    await repo.complete(
        attempt["study_id"],
        plan["revision"],
        attempt["id"],
        due,
        failures,
        error_code,
        now.isoformat(),
    )


class BillingScheduleService:
    async def require_study(self, db: aiosqlite.Connection, study_id: str) -> None:
        try:
            await StudyRepository(db).get(study_id)
        except KeyError as exc:
            raise AppError("Research not found", "STUDY_NOT_FOUND", 404) from exc

    async def read(
        self, db: aiosqlite.Connection, study_id: str, settings: Settings
    ) -> dict[str, Any]:
        await db.execute("BEGIN")
        try:
            await self.require_study(db, study_id)
            repo = BillingScheduleRepository(db)
            plan = await repo.current(study_id)
            config = await StudyBillingRepository(db).config(study_id)
            now = datetime.now(UTC)
            state = "not_configured"
            if plan:
                if not plan["enabled"]:
                    state = "paused"
                elif not config or plan["config_revision"] != config["revision"]:
                    state = "scope_changed"
                elif plan["next_due_at"] is None:
                    state = "attention"
                elif plan["error_code"]:
                    state = "retry_wait"
                elif plan["next_due_at"] <= now.isoformat():
                    state = "due"
                else:
                    state = "scheduled"
                if plan["last_attempt_id"] and state in ("scheduled", "retry_wait", "due"):
                    attempt = await StudyBillingRepository(db).attempt(
                        study_id, plan["last_attempt_id"]
                    )
                    if attempt and attempt["status"] == "running":
                        state = (
                            "running"
                            if (now - datetime.fromisoformat(attempt["started_at"])).total_seconds()
                            < 180
                            else "recovering"
                        )
            heartbeat = await repo.last_check()
            return {
                "study_id": study_id,
                "plan": plan,
                "config": config,
                "state": state,
                "history": await repo.history(study_id),
                "checked_at": heartbeat,
                "worker_enabled": settings.billing_scheduler_enabled,
                "worker_recent": bool(
                    settings.billing_scheduler_enabled
                    and heartbeat
                    and 0 <= (now - datetime.fromisoformat(heartbeat)).total_seconds() < 90
                ),
                "read_at": now.isoformat(),
            }
        finally:
            await db.rollback()

    async def configure(
        self, db: aiosqlite.Connection, study_id: str, body: BillingScheduleRequest
    ) -> dict[str, Any]:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self.require_study(db, study_id)
            repo = BillingScheduleRepository(db)
            plan = await repo.current(study_id)
            config = await StudyBillingRepository(db).config(study_id)
            if (plan["revision"] if plan else 0) != body.expected_revision:
                raise billing_error("BILLING_SCHEDULE_CONFLICT", 409)
            if not config or config["revision"] != body.expected_config_revision:
                raise billing_error("BILLING_CONFLICT", 409)
            if body.enabled and body.interval_minutes > config["max_age_hours"] * 30:
                raise billing_error("BILLING_SCHEDULE_INTERVAL", 422)
            now = datetime.now(UTC).isoformat()
            row = {
                "study_id": study_id,
                "revision": body.expected_revision + 1,
                "config_revision": config["revision"],
                "enabled": body.enabled,
                "interval_minutes": body.interval_minutes,
                "reason": body.reason,
                "created_at": now,
                "next_due_at": now if body.enabled else None,
            }
            await repo.save(row)
            await db.commit()
            return {
                **row,
                "last_attempt_id": None,
                "consecutive_failures": 0,
                "error_code": None,
                "updated_at": now,
            }
        except BaseException:
            await db.rollback()
            raise
