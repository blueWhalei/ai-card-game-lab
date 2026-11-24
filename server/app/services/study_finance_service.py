"""Recorded-cost accounting and admission limits, not a cap on actual spending."""

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.repositories.study_finance_repo import StudyFinanceRepository
from app.repositories.study_repo import StudyRepository
from app.schemas.study_finance import (
    BudgetRequest,
    ExpenseRequest,
    amount_text,
    amount_units,
)
from app.services.study_billing_service import ensure_supplier_budget
from app.utils.exceptions import AppError
from app.utils.id_generator import generate_id


def _budget(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    units = result.pop("limit_units")
    result["limit"] = amount_text(units) if units is not None else None
    result["enforcement_enabled"] = bool(result["enforcement_enabled"])
    return result


def _expense(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["amount"] = amount_text(result.pop("amount_units"))
    return result


async def ensure_study_budget(db: aiosqlite.Connection, experiment_id: str | None) -> None:
    """Caller owns the write transaction through task admission/commit."""
    if not experiment_id:
        return
    study_id = await StudyRepository(db).owner(experiment_id)
    if study_id is None:
        return
    repo = StudyFinanceRepository(db)
    budget = await repo.budget(study_id)
    if budget and budget["enforcement_enabled"]:
        total, _, _ = await repo.totals(study_id)
        if budget["limit_units"] is None or total >= budget["limit_units"]:
            raise AppError(
                "Registered expenses reached the research budget; new task admission is blocked. "
                "Review Budget and expenses in the research workspace.",
                "STUDY_BUDGET_REACHED",
                409,
            )
    await ensure_supplier_budget(db, study_id)


class StudyFinanceService:
    async def _require_study(self, db: aiosqlite.Connection, study_id: str) -> None:
        try:
            await StudyRepository(db).get(study_id)
        except KeyError as exc:
            raise AppError("Research not found", "STUDY_NOT_FOUND", 404) from exc

    async def read(self, db: aiosqlite.Connection, study_id: str, page: int) -> dict[str, Any]:
        await db.execute("BEGIN")
        try:
            await self._require_study(db, study_id)
            repo = StudyFinanceRepository(db)
            budget = await repo.budget(study_id)
            total, count, voided = await repo.totals(study_id)
            limit = budget["limit_units"] if budget else None
            return {
                "study_id": study_id,
                "page": page,
                "page_size": 20,
                "total": count + voided,
                "active_count": count,
                "voided_count": voided,
                "recorded_amount": amount_text(total) if count else None,
                "budget_difference": amount_text(limit - total)
                if limit is not None and count
                else None,
                "admission_blocked": bool(
                    budget and budget["enforcement_enabled"] and (limit is None or total >= limit)
                ),
                "budget": _budget(budget),
                "budget_history": [_budget(row) for row in await repo.history(study_id)],
                "items": [_expense(row) for row in await repo.expenses(study_id, page)],
                "read_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await db.rollback()

    async def set_budget(
        self, db: aiosqlite.Connection, study_id: str, body: BudgetRequest
    ) -> dict[str, Any] | None:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self._require_study(db, study_id)
            repo = StudyFinanceRepository(db)
            current = await repo.budget(study_id)
            revision = current["revision"] if current else 0
            if revision != body.expected_revision:
                raise AppError("Budget changed; reload before editing", "BUDGET_CONFLICT", 409)
            if current and current["currency"] != body.currency:
                raise AppError("Research currency cannot change", "BUDGET_CURRENCY_LOCKED", 409)
            data = {
                "study_id": study_id,
                "revision": revision + 1,
                "currency": body.currency,
                "limit_units": amount_units(body.limit) if body.limit is not None else None,
                "enforcement_enabled": body.enforcement_enabled,
                "reason": body.reason,
                "created_at": datetime.now(UTC).isoformat(),
            }
            await repo.add_budget(data)
            await db.commit()
            return _budget(data)
        except BaseException:
            await db.rollback()
            raise

    async def add_expense(
        self, db: aiosqlite.Connection, study_id: str, body: ExpenseRequest
    ) -> dict[str, Any]:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self._require_study(db, study_id)
            repo = StudyFinanceRepository(db)
            budget = await repo.budget(study_id)
            if not budget or budget["currency"] != body.currency:
                raise AppError("Save the matching research currency first", "EXPENSE_CURRENCY", 409)
            data = {
                **body.model_dump(mode="json", exclude={"amount"}),
                "amount_units": amount_units(body.amount),
                "study_id": study_id,
            }
            previous = await repo.by_request(study_id, body.request_id)
            if previous:
                if any(previous[key] != value for key, value in data.items()):
                    raise AppError("Request ID reused with different data", "EXPENSE_CONFLICT", 409)
                await db.rollback()
                return _expense(previous)
            data.update(id=generate_id("expense"), created_at=datetime.now(UTC).isoformat())
            try:
                await repo.add_expense(data)
            except aiosqlite.IntegrityError as exc:
                raise AppError(
                    "Source reference already registered", "EXPENSE_DUPLICATE", 409
                ) from exc
            await db.commit()
            return _expense({**data, "voided_at": None, "void_reason": None})
        except BaseException:
            await db.rollback()
            raise

    async def void_expense(
        self, db: aiosqlite.Connection, study_id: str, entry_id: str, reason: str
    ) -> dict[str, Any]:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await self._require_study(db, study_id)
            repo = StudyFinanceRepository(db)
            current = await repo.expense(study_id, entry_id)
            if current is None:
                raise AppError("Expense not found", "EXPENSE_NOT_FOUND", 404)
            if current["voided_at"]:
                if current["void_reason"] != reason:
                    raise AppError("Expense already voided", "EXPENSE_CONFLICT", 409)
            else:
                current.update(voided_at=datetime.now(UTC).isoformat(), void_reason=reason)
                await repo.void(study_id, entry_id, reason, current["voided_at"])
            await db.commit()
            return _expense(current)
        except BaseException:
            await db.rollback()
            raise
