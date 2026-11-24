"""Project-scoped supplier accounting, never a complete research cost estimate."""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import aiosqlite

from app.config import Settings
from app.repositories.billing_schedule_repo import BillingScheduleRepository
from app.repositories.study_billing_repo import StudyBillingRepository
from app.repositories.study_repo import StudyRepository
from app.schemas.study_billing import BillingConfigRequest
from app.services.billing_reconciliation_service import reconciliation_gate
from app.services.billing_schedule_service import finish_scheduled_attempt
from app.services.openai_costs import ENDPOINT, OpenAICostsClient, billing_error, exact_total
from app.utils.exceptions import AppError
from app.utils.id_generator import generate_id


def utc_now() -> datetime:
    return datetime.now(UTC)


async def billing_state(db: aiosqlite.Connection, study_id: str) -> dict[str, Any]:
    repo = StudyBillingRepository(db)
    config = await repo.config(study_id)
    snapshot = None
    latest = None
    state = "unconfigured"
    if config:
        attempts = await repo.attempts(study_id, config["revision"])
        latest = attempts[0] if attempts else None
        snapshot = await repo.latest_success(study_id, config["revision"])
        completed = next((attempt for attempt in attempts if attempt["status"] != "running"), None)
        if completed and completed["status"] in ("failed", "interrupted"):
            state = "failed"
        elif (
            latest
            and latest["status"] == "running"
            and (utc_now() - datetime.fromisoformat(latest["started_at"])).total_seconds() >= 180
        ):
            state = "interrupted"
        elif snapshot is None:
            state = "missing"
        elif utc_now().timestamp() - snapshot["end_time"] >= config["max_age_hours"] * 3600:
            state = "stale"
        elif config["limit_amount"] is not None and Decimal(snapshot["amount"]) >= Decimal(
            config["limit_amount"]
        ):
            state = "reached"
        else:
            state = "below"
    review_blocked = await reconciliation_gate(db, study_id)
    cost_blocked = bool(config and config["enforcement_enabled"] and state != "below")
    return {
        "config": config,
        "snapshot": snapshot,
        "latest_attempt": latest,
        "snapshot_valid_until": datetime.fromtimestamp(
            snapshot["end_time"] + config["max_age_hours"] * 3600, UTC
        ).isoformat()
        if snapshot and config
        else None,
        "state": state,
        "cost_admission_blocked": cost_blocked,
        "reconciliation_blocked": review_blocked,
        "admission_blocked": cost_blocked or review_blocked,
    }


async def ensure_supplier_budget(db: aiosqlite.Connection, study_id: str) -> None:
    state = await billing_state(db, study_id)
    if state["admission_blocked"]:
        code = (
            "SUPPLIER_RECONCILIATION_PENDING"
            if not state["cost_admission_blocked"]
            else (
                "SUPPLIER_BUDGET_REACHED"
                if state["state"] == "reached"
                else "SUPPLIER_BILLING_UNAVAILABLE"
            )
        )
        raise AppError(
            "Supplier cost admission limit prevents new tasks; review supplier billing", code, 409
        )


class StudyBillingService:
    async def require_study(self, db: aiosqlite.Connection, study_id: str) -> None:
        try:
            await StudyRepository(db).get(study_id)
        except KeyError as exc:
            raise AppError("Research not found", "STUDY_NOT_FOUND", 404) from exc

    def configured(self, settings: Settings) -> bool:
        return bool(
            settings.openai_billing_admin_key.get_secret_value().strip()
            and re.fullmatch(r"org-[a-zA-Z0-9_-]{1,120}", settings.openai_billing_organization_id)
        )

    async def read(
        self, db: aiosqlite.Connection, study_id: str, settings: Settings
    ) -> dict[str, Any]:
        await db.execute("BEGIN")
        try:
            await self.require_study(db, study_id)
            state = await billing_state(db, study_id)
            config = state["config"]
            return {
                "study_id": study_id,
                "provider": "openai",
                "source_url": ENDPOINT,
                "currency": "USD",
                "organization_id": settings.openai_billing_organization_id,
                "credential_configured": self.configured(settings),
                "can_sync": self.configured(settings)
                and bool(config)
                and config["organization_id"] == settings.openai_billing_organization_id,
                **state,
                "history": await StudyBillingRepository(db).attempts(study_id),
                "config_history": await StudyBillingRepository(db).config_history(study_id),
                "read_at": utc_now().isoformat(),
            }
        finally:
            await db.rollback()

    async def configure(
        self,
        db: aiosqlite.Connection,
        study_id: str,
        body: BillingConfigRequest,
        settings: Settings,
    ) -> dict[str, Any]:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self.require_study(db, study_id)
            repo = StudyBillingRepository(db)
            current = await repo.config(study_id)
            revision = current["revision"] if current else 0
            if revision != body.expected_revision:
                raise billing_error("BILLING_CONFLICT", 409)
            # Disabling remains possible if credentials were removed. New scopes require an org.
            organization = settings.openai_billing_organization_id or (current or {}).get(
                "organization_id", ""
            )
            if not re.fullmatch(r"org-[a-zA-Z0-9_-]{1,120}", organization):
                raise billing_error("BILLING_NOT_CONFIGURED", 409)
            row = {
                **body.model_dump(mode="json", exclude={"expected_revision", "limit"}),
                "study_id": study_id,
                "revision": revision + 1,
                "organization_id": organization,
                "limit_amount": body.limit,
                "created_at": utc_now().isoformat(),
            }
            await repo.save_config(row)
            await db.commit()
            return row
        except BaseException:
            await db.rollback()
            raise

    async def sync(
        self,
        db: aiosqlite.Connection,
        study_id: str,
        revision: int,
        settings: Settings,
        *,
        schedule_revision: int | None = None,
    ) -> dict[str, Any]:
        repo = StudyBillingRepository(db)
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self.require_study(db, study_id)
            config = await repo.config(study_id)
            if not config or config["revision"] != revision:
                raise billing_error("BILLING_CONFLICT", 409)
            now = utc_now()
            schedules = BillingScheduleRepository(db)
            plan = await schedules.current(study_id)
            if schedule_revision is not None and (
                not plan
                or not plan["enabled"]
                or plan["revision"] != schedule_revision
                or plan["config_revision"] != revision
                or plan["next_due_at"] is None
                or plan["next_due_at"] > now.isoformat()
            ):
                raise billing_error("BILLING_SCHEDULE_NOT_DUE", 409)
            active_plan = (
                plan if plan and plan["enabled"] and plan["config_revision"] == revision else None
            )
            history = await repo.attempts(study_id, revision)
            if history and history[0]["status"] == "running":
                previous = history[0]
                if (now - datetime.fromisoformat(previous["started_at"])).total_seconds() < 180:
                    if active_plan:
                        due = (
                            datetime.fromisoformat(previous["started_at"]) + timedelta(seconds=180)
                        ).isoformat()
                        await schedules.reserve(
                            study_id, active_plan["revision"], due, now.isoformat()
                        )
                        await db.commit()
                    raise billing_error("BILLING_BUSY", 409)
                await repo.finish(
                    previous["id"], "interrupted", now.isoformat(), "BILLING_INTERRUPTED"
                )
            attempt: dict[str, Any] = {
                "id": generate_id("billing"),
                "study_id": study_id,
                "revision": revision,
                "start_time": int(
                    datetime.fromisoformat(config["start_date"]).replace(tzinfo=UTC).timestamp()
                ),
                "end_time": int(now.timestamp()),
                "started_at": now.isoformat(),
                "trigger": "scheduled" if schedule_revision is not None else "manual",
                "schedule_revision": active_plan["revision"] if active_plan else None,
            }
            await repo.begin_attempt(attempt)
            if active_plan:
                await schedules.reserve(
                    study_id,
                    active_plan["revision"],
                    (now + timedelta(seconds=180)).isoformat(),
                    now.isoformat(),
                    attempt["id"],
                )
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
        # No SQLite write lock while awaiting the supplier. A saved configuration change
        # cannot adopt the old revision's response; snapshots remain tied to their revision.
        error: AppError | None = None
        items: list[dict[str, Any]] = []
        try:
            if (
                not self.configured(settings)
                or config["organization_id"] != settings.openai_billing_organization_id
            ):
                raise billing_error("BILLING_NOT_CONFIGURED", 409)
            items = await OpenAICostsClient(settings).fetch(
                config["project_id"], attempt["start_time"], attempt["end_time"]
            )
        except AppError as exc:
            error = exc
        except asyncio.CancelledError:
            await self._finish(db, attempt, "interrupted", "BILLING_INTERRUPTED", [])
            raise
        except Exception:
            error = billing_error("BILLING_RESPONSE")
        changed = await self._finish(
            db, attempt, "failed" if error else "succeeded", error.code if error else None, items
        )
        if error:
            raise error
        current = await repo.config(study_id)
        if not changed or current is None or current["revision"] != revision:
            raise billing_error("BILLING_CONFLICT", 409)
        return await self.read(db, study_id, settings)

    async def _finish(
        self,
        db: aiosqlite.Connection,
        attempt: dict[str, Any],
        status: str,
        error_code: str | None,
        items: list[dict[str, Any]],
    ) -> bool:
        await db.execute("BEGIN IMMEDIATE")
        try:
            now = utc_now()
            changed = await StudyBillingRepository(db).finish(
                attempt["id"],
                status,
                now.isoformat(),
                error_code,
                None if error_code else exact_total(items),
                None if error_code else json.dumps(items, ensure_ascii=False),
            )
            if changed:
                await finish_scheduled_attempt(db, attempt, error_code, now)
            await db.commit()
            return changed
        except BaseException:
            await db.rollback()
            raise

    async def evidence(
        self, db: aiosqlite.Connection, study_id: str, attempt_id: str, page: int
    ) -> dict[str, Any]:
        await self.require_study(db, study_id)
        attempt = await StudyBillingRepository(db).attempt(study_id, attempt_id)
        if attempt is None:
            raise AppError("Billing attempt not found", "BILLING_NOT_FOUND", 404)
        items = json.loads(attempt.pop("items_json") or "[]")
        return {
            **attempt,
            "source_url": ENDPOINT,
            "currency": "USD",
            "page": page,
            "page_size": 20,
            "total": len(items),
            "items": items[(page - 1) * 20 : page * 20],
        }
