"""Trace API endpoints for AI decision observability."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel

from app.dependencies import get_trace_service
from app.schemas.common import ApiResponse, PaginatedData
from app.services.trace_service import TraceService

router = APIRouter(tags=["traces"])


class TraceResponse(BaseModel):
    """Response model for a single trace."""

    id: str
    game_id: str
    round_number: int
    player_id: str
    model: str
    prompt_version: str
    input_snapshot: dict[str, Any]
    output_data: dict[str, Any]
    metrics: dict[str, Any]
    created_at: str
    spans: list[dict[str, Any]] | None = None


class MetricsResponse(BaseModel):
    """Response model for aggregated metrics."""

    total_traces: int
    response_time_count: int
    avg_response_time_ms: float | None
    min_response_time_ms: float | None
    max_response_time_ms: float | None
    parser_success_count: int
    parser_evaluated_count: int


def time_bounds(start: datetime | None, end: datetime | None) -> tuple[str | None, str | None]:
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="Start time must not be after end time")
    return (
        start.astimezone(UTC).isoformat() if start else None,
        end.astimezone(UTC).isoformat() if end else None,
    )


@router.get("", response_model=ApiResponse[PaginatedData[TraceResponse]])
async def list_traces(
    game_id: str | None = Query(None, description="Filter by game ID"),
    experiment_id: str | None = Query(None, description="Filter by experiment ID"),
    player_id: str | None = Query(None, description="Filter by player ID"),
    model: str | None = Query(None, description="Filter by model"),
    parser_ok: bool | None = Query(None, description="Filter by parser success (true/false)"),
    start_time: AwareDatetime | None = Query(None),
    end_time: AwareDatetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[PaginatedData[TraceResponse]]:
    """List traces with optional AND-combined filters."""
    start, end = time_bounds(start_time, end_time)
    offset = (page - 1) * page_size
    traces, total = await service.list_traces(
        game_id=game_id,
        experiment_id=experiment_id,
        player_id=player_id,
        model=model,
        parser_ok=parser_ok,
        start_time=start,
        end_time=end,
        limit=page_size,
        offset=offset,
    )

    return ApiResponse(
        data=PaginatedData(
            items=[TraceResponse(**t) for t in traces],
            total=total,
            page=page,
            page_size=page_size,
        ),
        message=f"Found {total} traces",
    )


@router.get("/metrics", response_model=ApiResponse[MetricsResponse])
async def get_metrics(
    game_id: str | None = Query(None, description="Filter by game ID"),
    experiment_id: str | None = Query(None, description="Filter by experiment ID"),
    player_id: str | None = Query(None, description="Filter by player ID"),
    model: str | None = Query(None, description="Filter by model"),
    parser_ok: bool | None = Query(None, description="Filter by parser success (true/false)"),
    start_time: AwareDatetime | None = Query(None, description="Start time (ISO with timezone)"),
    end_time: AwareDatetime | None = Query(None, description="End time (ISO with timezone)"),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[MetricsResponse]:
    """Get aggregated metrics for traces."""
    start, end = time_bounds(start_time, end_time)
    metrics = await service.get_metrics(
        game_id=game_id,
        experiment_id=experiment_id,
        player_id=player_id,
        model=model,
        parser_ok=parser_ok,
        start_time=start,
        end_time=end,
    )
    return ApiResponse(data=MetricsResponse(**metrics))


@router.get("/{trace_id}", response_model=ApiResponse[TraceResponse])
async def get_trace(
    trace_id: str,
    game_id: str | None = None,
    experiment_id: str | None = None,
    player_id: str | None = None,
    model: str | None = None,
    parser_ok: bool | None = None,
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[TraceResponse]:
    """Get a single trace by ID with its spans."""
    trace = await service.get_trace_by_id(
        trace_id,
        game_id=game_id,
        experiment_id=experiment_id,
        player_id=player_id,
        model=model,
        parser_ok=parser_ok,
    )
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return ApiResponse(data=TraceResponse(**trace))
