"""Puzzle pack API: extract, list, preview, run."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_puzzle_service
from app.schemas.common import ApiResponse
from app.schemas.puzzle import (
    DecisionPuzzleRequest,
    PuzzleExtractRequest,
    PuzzlePackSummary,
    PuzzleProbeRequest,
    PuzzleRunRequest,
)
from app.services.puzzle_service import PuzzleService

router = APIRouter(tags=["puzzles"])


@router.get("/decisions/{decision_id}", response_model=ApiResponse[dict[str, Any]])
async def inspect_decision_source(
    decision_id: str,
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.decision_source(decision_id))


@router.post("/from-decision", response_model=ApiResponse[dict[str, Any]])
async def create_decision_puzzle(
    body: DecisionPuzzleRequest,
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    manifest = await service.from_decision(
        body.decision_id,
        question=body.question,
        expected_source_hash=body.expected_source_hash,
    )
    return ApiResponse(data=_manifest_summary(manifest))


def _manifest_summary(manifest: Any) -> dict[str, Any]:
    return PuzzlePackSummary(
        pack_id=manifest.pack_id,
        created_at=manifest.created_at,
        game_type=manifest.game_type,
        source_experiment_id=manifest.source_experiment_id,
        puzzle_count=manifest.puzzle_count,
        extract=dict(manifest.extract or {}),
        notes=str(getattr(manifest, "notes", "") or ""),
        kind=str(getattr(manifest, "kind", "cardlab.puzzle_pack")),
        schema_version=int(getattr(manifest, "schema_version", 1)),
    ).model_dump()


@router.post("/extract", response_model=ApiResponse[dict[str, Any]])
async def extract_puzzles(
    body: PuzzleExtractRequest,
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    manifest = await service.extract(
        body.experiment_id,
        min_spread=body.min_spread,
        max_per_game=body.max_per_game,
        max_total=body.max_total,
    )
    return ApiResponse(data=_manifest_summary(manifest))


@router.get("/packs", response_model=ApiResponse[list[dict[str, Any]]])
async def list_puzzle_packs(
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[list[dict[str, Any]]]:
    packs = service.list_packs()
    return ApiResponse(data=[_manifest_summary(m) for m in packs])


@router.get("/packs/{pack_id}", response_model=ApiResponse[dict[str, Any]])
async def get_puzzle_pack(
    pack_id: str,
    preview: int = Query(default=5, ge=0, le=50),
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    manifest, puzzles = service.get_pack(pack_id, preview=preview)
    return ApiResponse(
        data={
            "manifest": _manifest_summary(manifest),
            "preview": [p.to_dict() for p in puzzles],
        }
    )


@router.post("/packs/{pack_id}/run", response_model=ApiResponse[dict[str, Any]])
async def run_puzzle_pack(
    pack_id: str,
    body: PuzzleRunRequest,
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    report = await service.run(
        pack_id,
        baseline_kind=body.baseline_kind,
        seed=body.seed,
    )
    return ApiResponse(data=report)


@router.get("/packs/{pack_id}/results", response_model=ApiResponse[dict[str, Any]])
def list_puzzle_results(
    pack_id: str,
    page: int = Query(default=1, ge=1, le=100000),
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=service.results(pack_id, page=page))


@router.get("/packs/{pack_id}/results/{run_id}", response_model=ApiResponse[dict[str, Any]])
def get_puzzle_result(
    pack_id: str,
    run_id: str,
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=service.result(pack_id, run_id))


@router.post("/packs/{pack_id}/probe", response_model=ApiResponse[dict[str, Any]])
async def probe_puzzle_pack(
    pack_id: str,
    body: PuzzleProbeRequest,
    service: PuzzleService = Depends(get_puzzle_service),
) -> ApiResponse[dict[str, Any]]:
    report = await service.probe(
        pack_id,
        baseline_kind=body.baseline_kind,
        seed=body.seed,
        n_trials=body.n_trials,
        kinds=[*body.kinds] if body.kinds is not None else None,
    )
    return ApiResponse(data=report)
