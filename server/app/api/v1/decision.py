"""Decision point API endpoints for SFT training data."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_decision_service
from app.schemas.common import ApiResponse
from app.services.decision_service import DecisionService

router = APIRouter(tags=["decision-points"])


class DecisionPointResponse(BaseModel):
    """Response model for a single decision point."""

    id: str
    game_id: str
    round_number: int
    player_id: str
    hand_cards: list[str]
    opponent_hands: dict[str, int] | None
    last_action: dict[str, Any] | None
    game_phase: str
    legal_actions: list[dict[str, Any]]
    chosen_action: dict[str, Any]
    thinking: str | None
    outcome: str | None
    quality_score: float
    created_at: str


class DecisionStatsResponse(BaseModel):
    """Response model for decision point statistics."""

    total: int
    avg_quality: float
    min_quality: float
    max_quality: float
    outcome_counts: dict[str, int]
    phase_counts: dict[str, int]


class ExportRequest(BaseModel):
    """Request model for exporting decision points."""

    game_id: str | None = None
    min_quality: float | None = None
    outcome: str | None = None


class ExportResponse(BaseModel):
    """Response model for export result."""

    filepath: str
    count: int


@router.get("", response_model=ApiResponse[list[DecisionPointResponse]])
async def list_decision_points(
    game_id: str | None = Query(None, description="Filter by game ID"),
    player_id: str | None = Query(None, description="Filter by player ID"),
    min_quality: float | None = Query(None, description="Minimum quality score"),
    max_quality: float | None = Query(None, description="Maximum quality score"),
    game_phase: str | None = Query(None, description="Filter by game phase"),
    outcome: str | None = Query(None, description="Filter by outcome (win/lose/draw)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: DecisionService = Depends(get_decision_service),
) -> ApiResponse[list[DecisionPointResponse]]:
    """List decision points with optional filters and pagination."""
    items, total = await service.list_decision_points(
        game_id=game_id,
        player_id=player_id,
        min_quality=min_quality,
        max_quality=max_quality,
        game_phase=game_phase,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )

    return ApiResponse(
        data=[DecisionPointResponse(**item) for item in items],
        message=f"Found {total} decision points",
    )


@router.get("/stats", response_model=ApiResponse[DecisionStatsResponse])
async def get_stats(
    service: DecisionService = Depends(get_decision_service),
) -> ApiResponse[DecisionStatsResponse]:
    """Get aggregate statistics for decision points."""
    stats = await service.get_stats()
    return ApiResponse(data=DecisionStatsResponse(**stats))


@router.post("/export", response_model=ApiResponse[ExportResponse])
async def export_chatml(
    request: ExportRequest,
    service: DecisionService = Depends(get_decision_service),
) -> ApiResponse[ExportResponse]:
    """Export decision points to ChatML format JSONL."""
    filepath = await service.export_chatml(
        game_id=request.game_id,
        min_quality=request.min_quality,
        outcome=request.outcome,
    )

    if not filepath:
        return ApiResponse(
            data=ExportResponse(filepath="", count=0),
            message="No decision points found to export",
        )

    _, count = await service.list_decision_points(
        game_id=request.game_id,
        min_quality=request.min_quality,
        outcome=request.outcome,
        limit=10000,
    )

    return ApiResponse(
        data=ExportResponse(filepath=filepath, count=count),
        message=f"Exported {count} decision points to {filepath}",
    )


@router.get("/{decision_id}", response_model=ApiResponse[DecisionPointResponse])
async def get_decision_point(
    decision_id: str,
    service: DecisionService = Depends(get_decision_service),
) -> ApiResponse[DecisionPointResponse]:
    """Get a single decision point by ID."""
    item = await service.get_decision_point(decision_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Decision point {decision_id} not found")
    return ApiResponse(data=DecisionPointResponse(**item))
