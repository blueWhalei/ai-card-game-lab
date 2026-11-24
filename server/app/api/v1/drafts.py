"""Draft HTTP boundary. Publication remains in the research API."""

import aiosqlite
from fastapi import APIRouter, Depends

from app.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.draft import DraftKind, DraftRecord, SaveDraftRequest
from app.services.draft_service import DraftConflictError, DraftService
from app.utils.exceptions import AppError

router = APIRouter()


@router.get("/{kind}/{object_id}")
async def read_draft(
    kind: DraftKind,
    object_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    service: DraftService = Depends(DraftService),
) -> ApiResponse[DraftRecord]:
    try:
        return ApiResponse(data=await service.read(db, kind, object_id))
    except KeyError as exc:
        raise AppError("Draft owner not found", "DRAFT_NOT_FOUND", 404) from exc


@router.put("/{kind}/{object_id}")
async def save_draft(
    kind: DraftKind,
    object_id: str,
    body: SaveDraftRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: DraftService = Depends(DraftService),
) -> ApiResponse[DraftRecord]:
    try:
        return ApiResponse(data=await service.save(db, kind, object_id, body))
    except KeyError as exc:
        raise AppError("Draft owner not found", "DRAFT_NOT_FOUND", 404) from exc
    except DraftConflictError as exc:
        raise AppError(str(exc), "DRAFT_CONFLICT", 409) from exc
    except ValueError as exc:
        raise AppError(str(exc), "DRAFT_INVALID", 422) from exc
