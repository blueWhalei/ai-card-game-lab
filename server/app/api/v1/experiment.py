"""Experiment (run) management endpoints."""

from __future__ import annotations

from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.dependencies import get_db, get_experiment_service
from app.schemas.common import ApiResponse
from app.schemas.experiment import (
    CloneExperimentRequest,
    CollectExperimentRequest,
    CreateExperimentRequest,
    ResearchRevisionRequest,
    SaveComparisonRequest,
    UpdateExperimentRequest,
)
from app.services.experiment_service import ExperimentNotFoundError, ExperimentService
from app.services.research_service import ResearchConflictError, ResearchValidationError

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
        prompt_version=body.prompt_version,
    )
    return ApiResponse(data=experiment)


@router.get("/compare")
async def compare_experiments(
    ids: str = "",
    allowed_changes: list[str] = Query(default=[]),
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    experiment_ids = [part.strip() for part in ids.split(",") if part.strip()]
    return ApiResponse(data=await service.compare_experiments(experiment_ids, allowed_changes))


@router.post("/comparisons", status_code=201)
async def save_comparison(
    body: SaveComparisonRequest, service: ExperimentService = Depends(get_experiment_service)
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(
        data=await service.save_comparison(body.experiment_ids, body.title, body.allowed_changes)
    )


@router.get("/comparisons")
async def list_comparisons(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=await service.list_comparisons(limit, offset))


@router.get("/comparisons/{snapshot_id}")
async def get_comparison(
    snapshot_id: str, service: ExperimentService = Depends(get_experiment_service)
) -> ApiResponse[dict[str, Any]]:
    try:
        return ApiResponse(data=await service.get_comparison(snapshot_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Comparison snapshot not found") from exc


@router.get("/comparisons/{comparison_id}/decisions")
async def research_candidates(
    comparison_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        return ApiResponse(data=await service.research_candidates(comparison_id, limit, offset))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Comparison snapshot not found") from exc


@router.get("/comparisons/{comparison_id}/conclusions")
async def research_versions(
    comparison_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        return ApiResponse(data=await service.research_versions(comparison_id, limit, offset))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Comparison snapshot not found") from exc


@router.post("/comparisons/{comparison_id}/conclusions", status_code=201)
async def save_research(
    comparison_id: str,
    body: ResearchRevisionRequest,
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        return ApiResponse(
            data=await service.save_research(
                comparison_id,
                body.expected_revision,
                body.observations,
                body.interpretation,
                body.limitations,
                [item.model_dump() for item in body.evidence],
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Comparison snapshot not found") from exc
    except ResearchConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ResearchValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/conclusions/{revision_id}")
async def get_research(
    revision_id: str, service: ExperimentService = Depends(get_experiment_service)
) -> ApiResponse[dict[str, Any]]:
    try:
        return ApiResponse(data=await service.get_research(revision_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conclusion revision not found") from exc


@router.get("/conclusions/{revision_id}/export")
async def export_research(
    revision_id: str, service: ExperimentService = Depends(get_experiment_service)
) -> ApiResponse[dict[str, Any]]:
    try:
        return ApiResponse(data=await service.get_research(revision_id, export=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conclusion revision not found") from exc


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


@router.post("/{experiment_id}/conclusion-draft")
async def conclusion_draft(
    experiment_id: str,
    locale: str | None = Query(default=None, description="zh-CN or en"),
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    """Assemble a conclusion draft (does not persist). Confirm via PATCH conclusion."""
    try:
        draft = await service.draft_conclusion(
            experiment_id, locale=locale or accept_language or "zh-CN"
        )
    except ExperimentNotFoundError:
        raise
    return ApiResponse(data=draft)


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
    result = await service.collect(
        experiment_id, count=body.count, db=db, idempotency_key=body.idempotency_key
    )
    return ApiResponse(data=result)


@router.post("/{experiment_id}/cancel-collect")
async def cancel_experiment_collect(
    experiment_id: str,
    service: ExperimentService = Depends(get_experiment_service),
) -> ApiResponse[dict[str, Any]]:
    """Stop in-flight collect by cancelling active games for this experiment."""
    result = await service.cancel_collect(experiment_id)
    return ApiResponse(data=result)
