"""Experiment (run) management endpoints."""

from __future__ import annotations

from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends

from app.dependencies import get_db, get_experiment_service
from app.schemas.common import ApiResponse
from app.schemas.experiment import (
    CloneExperimentRequest,
    CollectExperimentRequest,
    CreateExperimentRequest,
    UpdateExperimentRequest,
)
from app.services.experiment_service import ExperimentNotFoundError, ExperimentService

router = APIRouter()


@router.get("")
async def list_experiments(
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=await service.list_experiments())


@router.post("/import")
async def import_experiment_pack(
    body: dict[str, Any],
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.import_pack(body, include_experiment=True))


@router.post("", status_code=201)
async def create_experiment(
    body: CreateExperimentRequest,
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    experiment = await service.create_experiment(
        name=body.name,
        notes=body.notes,
        hypothesis=body.hypothesis,
        tags=body.tags,
        game_type=body.game_type,
        player_ids=body.player_ids,
        target_games=body.target_games,
        source_experiment_id=body.source_experiment_id,
        pair_deals=body.pair_deals,
        collect_mode=body.collect_mode,
    )
    return ApiResponse(data=experiment)


@router.get("/compare")
async def compare_experiments(
    ids: str = "",
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    experiment_ids = [part.strip() for part in ids.split(",") if part.strip()]
    return ApiResponse(data=await service.compare_experiments(experiment_ids))


@router.get("/{experiment_id}")
async def get_experiment(
    experiment_id: str,
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        experiment = await service.get_experiment(experiment_id)
    except ExperimentNotFoundError:
        raise
    return ApiResponse(data=experiment)


@router.get("/{experiment_id}/export")
async def export_experiment_pack(
    experiment_id: str,
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        pack = await service.export_pack(experiment_id)
    except ExperimentNotFoundError:
        raise
    return ApiResponse(data=pack)


@router.patch("/{experiment_id}")
async def update_experiment(
    experiment_id: str,
    body: UpdateExperimentRequest,
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        experiment = await service.update_experiment(
            experiment_id,
            name=body.name,
            notes=body.notes,
            hypothesis=body.hypothesis,
            conclusion=body.conclusion,
            tags=body.tags,
        )
    except ExperimentNotFoundError:
        raise
    return ApiResponse(data=experiment)


@router.post("/{experiment_id}/clone", status_code=201)
async def clone_experiment(
    experiment_id: str,
    body: CloneExperimentRequest,
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        experiment = await service.clone_experiment(
            experiment_id,
            name=body.name,
            copy_deal_seeds=body.copy_deal_seeds,
            copy_hypothesis=body.copy_hypothesis,
        )
    except ExperimentNotFoundError:
        raise
    return ApiResponse(data=experiment)


@router.post("/{experiment_id}/collect", status_code=201)
async def collect_experiment(
    experiment_id: str,
    body: CollectExperimentRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.collect(experiment_id, count=body.count, db=db)
    return ApiResponse(data=result)
