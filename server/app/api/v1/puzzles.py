"""Puzzle pack API: extract, list, preview, run."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_puzzle_service
from app.schemas.common import ApiResponse
from app.schemas.puzzle import PuzzleExtractRequest, PuzzlePackSummary, PuzzleRunRequest
from app.services.puzzle_service import PuzzleService

router = APIRouter(tags=["puzzles"])


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
