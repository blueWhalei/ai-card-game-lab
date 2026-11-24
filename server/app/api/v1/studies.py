"""Research workspace endpoints."""

from typing import Any, Literal

import aiosqlite
from fastapi import APIRouter, Depends, Query

from app.api.v1.billing_reconciliation import router as reconciliation_router
from app.config import Settings
from app.dependencies import get_db, get_experiment_service, get_settings
from app.schemas.common import ApiResponse
from app.schemas.study import AttachStudyRunRequest, CreateStudyRequest
from app.schemas.study_billing import (
    BillingConfigRequest,
    BillingScheduleRequest,
    BillingSyncRequest,
)
from app.schemas.study_finance import BudgetRequest, ExpenseRequest, VoidExpenseRequest
from app.services.billing_schedule_service import BillingScheduleService
from app.services.experiment_service import ExperimentService
from app.services.study_billing_service import StudyBillingService
from app.services.study_finance_service import StudyFinanceService
from app.services.study_service import StudyService

router = APIRouter()
router.include_router(reconciliation_router)


@router.get("/{study_id}/billing/schedule")
async def billing_schedule(
    study_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: BillingScheduleService = Depends(BillingScheduleService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.read(db, study_id, settings))


@router.put("/{study_id}/billing/schedule")
async def configure_billing_schedule(
    study_id: str,
    body: BillingScheduleRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingScheduleService = Depends(BillingScheduleService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.configure(db, study_id, body))


@router.get("/{study_id}/billing")
async def study_billing(
    study_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: StudyBillingService = Depends(StudyBillingService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.read(db, study_id, settings))


@router.put("/{study_id}/billing/config")
async def configure_billing(
    study_id: str,
    body: BillingConfigRequest,
    db: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: StudyBillingService = Depends(StudyBillingService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.configure(db, study_id, body, settings))


@router.post("/{study_id}/billing/sync")
async def sync_billing(
    study_id: str,
    body: BillingSyncRequest,
    db: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: StudyBillingService = Depends(StudyBillingService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.sync(db, study_id, body.expected_revision, settings))


@router.get("/{study_id}/billing/attempts/{attempt_id}")
async def billing_evidence(
    study_id: str,
    attempt_id: str,
    page: int = Query(default=1, ge=1, le=1000000),
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyBillingService = Depends(StudyBillingService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.evidence(db, study_id, attempt_id, page))


@router.get("/{study_id}/finance")
async def study_finance(
    study_id: str,
    page: int = Query(default=1, ge=1, le=1000000),
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyFinanceService = Depends(StudyFinanceService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.read(db, study_id, page))


@router.put("/{study_id}/budget")
async def set_budget(
    study_id: str,
    body: BudgetRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyFinanceService = Depends(StudyFinanceService),
) -> ApiResponse[dict[str, Any] | None]:
    return ApiResponse(data=await service.set_budget(db, study_id, body))


@router.post("/{study_id}/expenses", status_code=201)
async def add_expense(
    study_id: str,
    body: ExpenseRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyFinanceService = Depends(StudyFinanceService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.add_expense(db, study_id, body))


@router.post("/{study_id}/expenses/{entry_id}/void")
async def void_expense(
    study_id: str,
    entry_id: str,
    body: VoidExpenseRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyFinanceService = Depends(StudyFinanceService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.void_expense(db, study_id, entry_id, body.reason))


@router.get("/{study_id}/operations")
async def study_operations(
    study_id: str,
    state: Literal["all", "active", "attention"] = "all",
    page: int = Query(default=1, ge=1, le=1000000),
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyService = Depends(StudyService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.operations(db, study_id, state, page))


@router.get("")
async def list_studies(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyService = Depends(StudyService),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=await service.list(db, limit, offset))


@router.post("", status_code=201)
async def create_study(
    body: CreateStudyRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyService = Depends(StudyService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.create(db, body))


@router.get("/{study_id}")
async def get_study(
    study_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyService = Depends(StudyService),
    experiments: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.workspace(db, study_id, experiments))


@router.post("/{study_id}/runs")
async def attach_run(
    study_id: str,
    body: AttachStudyRunRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: StudyService = Depends(StudyService),
) -> ApiResponse[dict[str, bool]]:
    await service.attach(db, study_id, body.experiment_id)
    return ApiResponse(data={"attached": True})
