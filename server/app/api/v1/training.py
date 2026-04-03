"""Training management API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_training_service
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.training import CreateTrainingTaskRequest
from app.services.training_service import TrainingService

router = APIRouter()


@router.get("/training/tasks")
async def list_training_tasks(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: TrainingService = Depends(get_training_service),
) -> ApiResponse[PaginatedData[dict[str, Any]]]:
    items, total = await service.list_tasks(status=status, page=page, page_size=page_size)
    return ApiResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size),
    )


@router.post("/training/tasks", status_code=201)
async def create_training_task(
    body: CreateTrainingTaskRequest,
    service: TrainingService = Depends(get_training_service),
) -> ApiResponse[dict[str, Any]]:
    task = await service.create_task(body)
    return ApiResponse(data=task)


@router.get("/training/tasks/{task_id}")
async def get_training_task(
    task_id: str,
    service: TrainingService = Depends(get_training_service),
) -> ApiResponse[dict[str, Any]]:
    task = await service.get_task(task_id)
    return ApiResponse(data=task)


@router.delete("/training/tasks/{task_id}")
async def delete_training_task(
    task_id: str,
    service: TrainingService = Depends(get_training_service),
) -> ApiResponse[dict[str, str]]:
    await service.delete_task(task_id)
    return ApiResponse(data={"status": "deleted"})


@router.get("/models")
async def list_models(
    service: TrainingService = Depends(get_training_service),
) -> ApiResponse[list[dict[str, Any]]]:
    models = await service.list_models()
    return ApiResponse(data=models)


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    service: TrainingService = Depends(get_training_service),
) -> ApiResponse[dict[str, str]]:
    await service.delete_model(model_id)
    return ApiResponse(data={"status": "deleted"})
