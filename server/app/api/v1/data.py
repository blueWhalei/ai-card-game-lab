"""Data management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_data_service
from app.schemas.common import ApiResponse
from app.schemas.data import CreateDatasetRequest
from app.services.data_service import DataService

router = APIRouter()


@router.get("/data/stats")
async def data_stats(
    service: DataService = Depends(get_data_service),
) -> ApiResponse[dict[str, Any]]:
    """Overall data statistics."""
    stats = await service.get_stats()
    return ApiResponse(data=stats)


@router.get("/datasets")
async def list_datasets(
    service: DataService = Depends(get_data_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """List all datasets."""
    datasets = await service.list_datasets()
    return ApiResponse(data=datasets)


@router.post("/datasets", status_code=201)
async def create_dataset(
    body: CreateDatasetRequest,
    service: DataService = Depends(get_data_service),
) -> ApiResponse[dict[str, Any]]:
    """Create a dataset from filtered game data."""
    dataset = await service.create_dataset(body)
    return ApiResponse(data=dataset)


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    service: DataService = Depends(get_data_service),
) -> ApiResponse[dict[str, Any]]:
    """Get dataset details."""
    dataset = await service.get_dataset(dataset_id)
    return ApiResponse(data=dataset)


@router.delete("/datasets/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: str,
    service: DataService = Depends(get_data_service),
) -> None:
    """Delete a dataset and its file."""
    await service.delete_dataset(dataset_id)
