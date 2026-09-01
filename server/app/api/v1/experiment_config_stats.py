"""Experiment config statistics API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import (
    get_experiment_config_service,
    get_experiment_config_stats_service,
)
from app.schemas.common import ApiResponse
from app.services.experiment_config_service import ExperimentConfigService
from app.services.experiment_config_stats_service import ExperimentConfigStatsService

router = APIRouter()


@router.get("/stats")
async def get_all_configs_stats(
    config_service: ExperimentConfigService = Depends(get_experiment_config_service),
    stats_service: ExperimentConfigStatsService = Depends(get_experiment_config_stats_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Get statistics for all registered experiment configs."""
    config_ids = [c["id"] for c in config_service.list_configs()]
    stats = await stats_service.get_all_stats(config_ids)
    return ApiResponse(data=stats)
