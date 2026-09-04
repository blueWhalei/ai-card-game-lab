"""Experiment config management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from app.core.pack import parse_pack
from app.dependencies import get_experiment_config_service
from app.schemas.common import ApiResponse
from app.schemas.experiment_config import (
    CreateExperimentConfigRequest,
    UpdateExperimentConfigRequest,
)
from app.services.experiment_config_service import ExperimentConfigService
from app.utils.exceptions import AppError

router = APIRouter()


class ExperimentConfigNotFoundError(AppError):
    def __init__(self, config_id: str) -> None:
        super().__init__(
            message=f"Experiment config not found: {config_id}",
            code="EXPERIMENT_CONFIG_NOT_FOUND",
            status_code=404,
        )


class ExperimentConfigConflictError(AppError):
    def __init__(self, config_id: str) -> None:
        super().__init__(
            message=f"Experiment config already exists: {config_id}",
            code="EXPERIMENT_CONFIG_CONFLICT",
            status_code=409,
        )


class ExperimentConfigValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="EXPERIMENT_CONFIG_VALIDATION_FAILED",
            status_code=400,
        )


@router.get("")
async def list_experiment_configs(
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=service.list_configs())


@router.post("", status_code=201)
async def create_experiment_config(
    body: CreateExperimentConfigRequest,
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        config = await service.create_config(
            {
                "id": body.id,
                "name": body.name,
                "notes": body.notes,
                "model_config": body.model_config_data.model_dump(),
            }
        )
    except ValueError as e:
        raise ExperimentConfigConflictError(body.id) from e
    return ApiResponse(data=config)


@router.get("/export")
async def export_experiment_configs(
    ids: str = "",
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> ApiResponse[dict[str, Any]]:
    wanted = [part.strip() for part in ids.split(",") if part.strip()] or None
    return ApiResponse(data=service.export_pack(wanted))


@router.post("/import")
async def import_experiment_configs(
    body: dict[str, Any],
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        pack = parse_pack(body)
    except ValueError as exc:
        raise ExperimentConfigValidationError(str(exc)) from exc
    result = await service.import_players(list(pack.get("players") or []))
    return ApiResponse(
        data={
            "kind": pack["kind"],
            "players_created": result["created"],
            "players_reused": result["reused"],
            "requirements": pack.get("requirements") or {},
        }
    )


@router.get("/{config_id}")
async def get_experiment_config(
    config_id: str,
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> ApiResponse[dict[str, Any]]:
    config = service.get_config(config_id)
    if not config:
        raise ExperimentConfigNotFoundError(config_id)
    return ApiResponse(data=config)


@router.put("/{config_id}")
async def update_experiment_config(
    config_id: str,
    body: UpdateExperimentConfigRequest,
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> ApiResponse[dict[str, Any]]:
    update_data: dict[str, Any] = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.notes is not None:
        update_data["notes"] = body.notes
    if body.model_config_data is not None:
        update_data["model_config"] = body.model_config_data.model_dump()

    try:
        config = await service.update_config(config_id, update_data)
    except KeyError as e:
        raise ExperimentConfigNotFoundError(config_id) from e
    return ApiResponse(data=config)


async def _delete_config(config_id: str, service: ExperimentConfigService) -> Response:
    try:
        await service.delete_config(config_id)
    except KeyError as e:
        raise ExperimentConfigNotFoundError(config_id or "(empty)") from e
    return Response(status_code=204)


@router.delete("", status_code=204, response_class=Response)
async def delete_experiment_config_by_query(
    id: str = Query(..., description="Config id; send empty string to remove a blank-id row"),
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> Response:
    """Delete by query so blank ids are addressable (path DELETE /{id} cannot encode '')."""
    return await _delete_config(id, service)


@router.delete("/{config_id}", status_code=204, response_class=Response)
async def delete_experiment_config(
    config_id: str,
    service: ExperimentConfigService = Depends(get_experiment_config_service),
) -> Response:
    return await _delete_config(config_id, service)
