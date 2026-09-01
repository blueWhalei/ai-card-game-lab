"""Decision point API endpoints for SFT training data."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies import get_decision_service
from app.schemas.common import ApiResponse, PaginatedData
from app.services.decision_service import DecisionService

router = APIRouter(tags=["decision-points"])


class DecisionPointResponse(BaseModel):
    """Response model for a single decision point."""

    id: str
    game_id: str
    round_number: int
    player_id: str
    hand_cards: list[Any]
    opponent_hands: dict[str, int] | None
    last_action: dict[str, Any] | None
    game_phase: str
    legal_actions: list[dict[str, Any]]
    chosen_action: dict[str, Any]
    thinking: str | None
    outcome: str | None
    quality_score: float
    train_usable: bool = True
    created_at: str


class DecisionStatsResponse(BaseModel):
    """Response model for decision point statistics."""

    total: int
    avg_quality: float
    min_quality: float
    max_quality: float
    outcome_counts: dict[str, int]
    phase_counts: dict[str, int]
    train_usable_count: int = 0
    not_usable_count: int = 0
    usable_rate: float = 0.0


class ExportRequest(BaseModel):
    """Request model for exporting decision points."""

    game_id: str | None = None
    experiment_id: str | None = None
    player_id: str | None = None
    min_quality: float | None = None
    outcome: str | None = None
    game_phase: str | None = None
    train_usable: bool | None = Field(
        default=None,
        description="Exact train_usable filter; overrides train_usable_only when set",
    )
    train_usable_only: bool = Field(
        default=True,
        description="Only export samples marked train_usable=true (ignored if train_usable set)",
    )
    include_thinking: bool = Field(
        default=False,
        description="Include chain-of-thought text in assistant messages",
    )


class ExportResponse(BaseModel):
    """Response model for export result."""

    filepath: str
    count: int


@router.get("", response_model=ApiResponse[PaginatedData[DecisionPointResponse]])
async def list_decision_points(
    game_id: str | None = Query(None, description="Filter by game ID"),
    experiment_id: str | None = Query(None, description="Filter by experiment ID"),
    player_id: str | None = Query(None, description="Filter by player ID"),
    min_quality: float | None = Query(None, description="Minimum quality score"),
    max_quality: float | None = Query(None, description="Maximum quality score"),
    game_phase: str | None = Query(None, description="Filter by game phase"),
    outcome: str | None = Query(None, description="Filter by outcome (win/lose/draw)"),
    train_usable: bool | None = Query(
        None, description="Filter by train_usable flag (true/false)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    service: DecisionService = Depends(get_decision_service),
) -> ApiResponse[PaginatedData[DecisionPointResponse]]:
    """List decision points with optional filters and pagination."""
    offset = (page - 1) * page_size
    items, total = await service.list_decision_points(
        game_id=game_id,
        experiment_id=experiment_id,
        player_id=player_id,
        min_quality=min_quality,
        max_quality=max_quality,
        game_phase=game_phase,
        outcome=outcome,
        train_usable=train_usable,
        limit=page_size,
        offset=offset,
    )

    return ApiResponse(
        data=PaginatedData(
            items=[DecisionPointResponse(**item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        ),
        message=f"Found {total} decision points",
    )


@router.get("/stats", response_model=ApiResponse[DecisionStatsResponse])
async def get_stats(
    experiment_id: str | None = Query(None, description="Filter by experiment ID"),
    service: DecisionService = Depends(get_decision_service),
) -> ApiResponse[DecisionStatsResponse]:
    """Get aggregate statistics for decision points."""
    stats = await service.get_stats(experiment_id=experiment_id)
    return ApiResponse(data=DecisionStatsResponse(**stats))


@router.post("/export", response_model=ApiResponse[ExportResponse])
async def export_chatml(
    request: ExportRequest,
    service: DecisionService = Depends(get_decision_service),
) -> ApiResponse[ExportResponse]:
    """Export decision points to ChatML format JSONL."""
    filepath, count, _split = await service.export_chatml(
        game_id=request.game_id,
        experiment_id=request.experiment_id,
        player_id=request.player_id,
        min_quality=request.min_quality,
        outcome=request.outcome,
        game_phase=request.game_phase,
        train_usable=request.train_usable,
        train_usable_only=request.train_usable_only,
        include_thinking=request.include_thinking,
    )

    if not filepath:
        return ApiResponse(
            data=ExportResponse(filepath="", count=0),
            message="No decision points found to export",
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
