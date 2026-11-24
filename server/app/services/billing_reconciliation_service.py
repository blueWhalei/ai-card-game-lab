"""Scoped arithmetic comparison, not verification of invoices or complete research costs."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Any

import aiosqlite

from app.repositories.billing_reconciliation_repo import BillingReconciliationRepository
from app.repositories.study_billing_repo import StudyBillingRepository
from app.repositories.study_repo import StudyRepository
from app.schemas.billing_reconciliation import (
    ReconciliationCsvFile,
    ReconciliationInput,
    ReconciliationPolicyRequest,
    ReconciliationReviewRequest,
    SaveReconciliationRequest,
)
from app.services.billing_reconciliation_csv import csv_evidence, read_csv
from app.services.openai_costs import ENDPOINT, exact_total
from app.utils.exceptions import AppError
from app.utils.id_generator import generate_id


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def error(code: str, status: int = 409) -> AppError:
    return AppError("Cost reconciliation requires review", code, status)


def present(row: dict[str, Any]) -> dict[str, Any]:
    comparison = json.loads(row["comparison_json"])
    return {
        "id": row["id"],
        "study_id": row["study_id"],
        "created_at": row["created_at"],
        "comparison": comparison,
        "review_revision": row["review_revision"],
        "review_action": row["review_action"],
        "review_reason": row["review_reason"],
        "reviewed_at": row["reviewed_at"],
        "pending": row["result"] != "matched" and row["review_action"] in (None, "reopen"),
    }


async def reconciliation_gate(db: aiosqlite.Connection, study_id: str) -> bool:
    repo = BillingReconciliationRepository(db)
    policy = await repo.policy(study_id)
    return bool(policy and policy["enabled"] and await repo.pending_count(study_id))


class BillingReconciliationService:
    async def require_study(self, db: aiosqlite.Connection, study_id: str) -> None:
        try:
            await StudyRepository(db).get(study_id)
        except KeyError as exc:
            raise AppError("Research not found", "STUDY_NOT_FOUND", 404) from exc

    async def csv_columns(
        self, db: aiosqlite.Connection, study_id: str, body: ReconciliationCsvFile
    ) -> list[str]:
        await self.require_study(db, study_id)
        _, header, _ = read_csv(body.content_base64)
        return header

    async def calculate(
        self, db: aiosqlite.Connection, study_id: str, body: ReconciliationInput
    ) -> dict[str, Any]:
        await self.require_study(db, study_id)
        attempt = await StudyBillingRepository(db).attempt(study_id, body.attempt_id)
        if not attempt or attempt["status"] != "succeeded":
            raise error("RECONCILIATION_SOURCE", 409)
        start = int(datetime.combine(body.period_start, datetime.min.time(), UTC).timestamp())
        end = int(datetime.combine(body.period_end, datetime.min.time(), UTC).timestamp())
        reasons = []
        if body.source_type not in ("cost_export", "invoice_project_subtotal"):
            reasons.append("basis")
        if body.organization_id != attempt["organization_id"]:
            reasons.append("organization")
        if body.project_id != attempt["project_id"]:
            reasons.append("project")
        if body.currency != "USD":
            reasons.append("currency")
        if not attempt["start_time"] <= start < end <= attempt["end_time"]:
            reasons.append("period")
        try:
            items = json.loads(attempt["items_json"])
            if not isinstance(items, list):
                raise ValueError()
            selected = []
            crosses_boundary = False
            for item in items:
                left, right = item["start_time"], item["end_time"]
                amount = Decimal(item["amount"])
                exponent = amount.as_tuple().exponent
                if (
                    type(left) is not int
                    or type(right) is not int
                    or not attempt["start_time"] <= left < right <= attempt["end_time"]
                    or item["currency"] != "USD"
                    or item["project_id"] != attempt["project_id"]
                    or not amount.is_finite()
                    or abs(amount) > 10**12
                    or not isinstance(exponent, int)
                    or exponent < -18
                ):
                    raise ValueError()
                if left < end and right > start:
                    if left < start or right > end:
                        crosses_boundary = True
                    else:
                        selected.append(item)
            if crosses_boundary:
                reasons.append("bucket_boundary")
            if Decimal(exact_total(items)) != Decimal(attempt["amount"]):
                raise ValueError()
        except (ValueError, TypeError, KeyError, ArithmeticError):
            raise error("RECONCILIATION_SOURCE") from None
        source_amount = body.source_amount
        csv_metadata = None
        if body.csv is not None:
            source_amount, csv_metadata = csv_evidence(body)
        assert source_amount is not None
        interface_amount = exact_total(selected) if not reasons else None
        difference = None
        if interface_amount is not None:
            with localcontext() as context:
                context.prec = 60
                difference = format(Decimal(interface_amount) - Decimal(source_amount), "f")
        result = (
            "not_comparable"
            if reasons
            else "matched"
            if Decimal(difference or "0") == 0
            else "difference"
        )
        comparison = {
            "calculation_version": "project-cost-reconciliation-v1",
            "input": {
                **body.model_dump(mode="json", exclude={"csv"}),
                "source_amount": source_amount,
            },
            "result": result,
            "reasons": reasons,
            "interface_amount": interface_amount,
            "difference": difference,
            "included_line_count": len(selected) if not reasons else None,
            "snapshot": {
                key: attempt[key]
                for key in (
                    "id",
                    "revision",
                    "organization_id",
                    "project_id",
                    "start_time",
                    "end_time",
                    "finished_at",
                    "amount",
                    "trigger",
                    "schedule_revision",
                )
            },
            "source_url": ENDPOINT,
        }
        if csv_metadata is not None:
            comparison["csv_evidence"] = csv_metadata
        return {**comparison, "preview_hash": digest({"comparison": comparison, "items": items})}

    async def preview(
        self, db: aiosqlite.Connection, study_id: str, body: ReconciliationInput
    ) -> dict[str, Any]:
        await db.execute("BEGIN")
        try:
            return await self.calculate(db, study_id, body)
        finally:
            await db.rollback()

    async def save(
        self, db: aiosqlite.Connection, study_id: str, body: SaveReconciliationRequest
    ) -> dict[str, Any]:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self.require_study(db, study_id)
            repo = BillingReconciliationRepository(db)
            exclude = {"request_id"} if body.csv is not None else {"request_id", "csv"}
            payload = body.model_dump(mode="json", exclude=exclude)
            existing = await repo.request(study_id, body.request_id)
            if existing:
                if existing["request_hash"] != digest(payload):
                    raise error("RECONCILIATION_CONFLICT")
                await db.commit()
                return present(existing)
            source = ReconciliationInput.model_validate(
                body.model_dump(exclude={"request_id", "expected_preview_hash"})
            )
            comparison = await self.calculate(db, study_id, source)
            if comparison["preview_hash"] != body.expected_preview_hash:
                raise error("RECONCILIATION_CHANGED")
            record_id = generate_id("reconciliation")
            await repo.save(
                {
                    "id": record_id,
                    "study_id": study_id,
                    "attempt_id": body.attempt_id,
                    "request_id": body.request_id,
                    "request_hash": digest(payload),
                    "result": comparison["result"],
                    "comparison_json": canonical(comparison),
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            row = await repo.record(study_id, record_id)
            assert row is not None
            await db.commit()
            return present(row)
        except BaseException:
            await db.rollback()
            raise

    async def read(self, db: aiosqlite.Connection, study_id: str, page: int) -> dict[str, Any]:
        await db.execute("BEGIN")
        try:
            await self.require_study(db, study_id)
            repo = BillingReconciliationRepository(db)
            records, total = await repo.records(study_id, page)
            policy = await repo.policy(study_id)
            pending = await repo.pending_count(study_id)
            return {
                "study_id": study_id,
                "policy": policy,
                "policy_history": await repo.policy_history(study_id),
                "pending_count": pending,
                "admission_blocked": bool(policy and policy["enabled"] and pending),
                "records": [present(row) for row in records],
                "page": page,
                "page_size": 10,
                "total": total,
                "read_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await db.rollback()

    async def detail(
        self, db: aiosqlite.Connection, study_id: str, record_id: str
    ) -> dict[str, Any]:
        await db.execute("BEGIN")
        try:
            await self.require_study(db, study_id)
            repo = BillingReconciliationRepository(db)
            row = await repo.record(study_id, record_id)
            if not row:
                raise error("RECONCILIATION_NOT_FOUND", 404)
            return {**present(row), "reviews": await repo.reviews(record_id)}
        finally:
            await db.rollback()

    async def set_policy(
        self, db: aiosqlite.Connection, study_id: str, body: ReconciliationPolicyRequest
    ) -> dict[str, Any]:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self.require_study(db, study_id)
            repo = BillingReconciliationRepository(db)
            previous = await repo.policy(study_id)
            if (previous["revision"] if previous else 0) != body.expected_revision:
                raise error("RECONCILIATION_CONFLICT")
            row = {
                "study_id": study_id,
                "revision": body.expected_revision + 1,
                "enabled": body.enabled,
                "reason": body.reason,
                "created_at": datetime.now(UTC).isoformat(),
            }
            await repo.set_policy(row)
            await db.commit()
            return row
        except BaseException:
            await db.rollback()
            raise

    async def review(
        self,
        db: aiosqlite.Connection,
        study_id: str,
        record_id: str,
        body: ReconciliationReviewRequest,
    ) -> dict[str, Any]:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self.require_study(db, study_id)
            repo = BillingReconciliationRepository(db)
            row = await repo.record(study_id, record_id)
            if not row:
                raise error("RECONCILIATION_NOT_FOUND", 404)
            if row["review_revision"] != body.expected_revision:
                raise error("RECONCILIATION_CONFLICT")
            if row["review_action"] == "void" or (
                row["result"] == "matched" and body.action != "void"
            ):
                raise error("RECONCILIATION_REVIEW")
            await repo.review(
                {
                    "record_id": record_id,
                    "revision": body.expected_revision + 1,
                    "action": body.action,
                    "reason": body.reason,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            updated = await repo.record(study_id, record_id)
            assert updated is not None
            await db.commit()
            return present(updated)
        except BaseException:
            await db.rollback()
            raise
