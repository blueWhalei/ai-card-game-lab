"""Research-scoped reconciliation; all accounting logic stays in services."""

from collections.abc import Callable, Coroutine
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.dependencies import get_db
from app.schemas.billing_reconciliation import (
    ReconciliationCsvFile,
    ReconciliationInput,
    ReconciliationPolicyRequest,
    ReconciliationReviewRequest,
    SaveReconciliationRequest,
)
from app.schemas.common import ApiResponse
from app.services.billing_reconciliation_service import BillingReconciliationService


class ReconciliationRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError as exc:
                # Validation errors can otherwise echo the uploaded file or an entire input body.
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": [
                            {key: item[key] for key in ("loc", "type", "msg")}
                            for item in exc.errors()
                        ]
                    },
                )

        return handle


router = APIRouter(prefix="/{study_id}/billing/reconciliations", route_class=ReconciliationRoute)


@router.get("")
async def reconciliations(
    study_id: str,
    page: int = Query(default=1, ge=1, le=1000000),
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingReconciliationService = Depends(BillingReconciliationService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.read(db, study_id, page))


@router.post("/preview")
async def preview(
    study_id: str,
    body: ReconciliationInput,
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingReconciliationService = Depends(BillingReconciliationService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.preview(db, study_id, body))


@router.post("/csv-columns")
async def csv_columns(
    study_id: str,
    body: ReconciliationCsvFile,
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingReconciliationService = Depends(BillingReconciliationService),
) -> ApiResponse[list[str]]:
    return ApiResponse(data=await service.csv_columns(db, study_id, body))


@router.put("/policy")
async def policy(
    study_id: str,
    body: ReconciliationPolicyRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingReconciliationService = Depends(BillingReconciliationService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.set_policy(db, study_id, body))


@router.post("")
async def save(
    study_id: str,
    body: SaveReconciliationRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingReconciliationService = Depends(BillingReconciliationService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.save(db, study_id, body))


@router.get("/{record_id}")
async def detail(
    study_id: str,
    record_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingReconciliationService = Depends(BillingReconciliationService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.detail(db, study_id, record_id))


@router.post("/{record_id}/reviews")
async def review(
    study_id: str,
    record_id: str,
    body: ReconciliationReviewRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: BillingReconciliationService = Depends(BillingReconciliationService),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.review(db, study_id, record_id, body))
