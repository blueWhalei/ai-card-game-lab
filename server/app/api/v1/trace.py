"""Trace API endpoints for AI decision observability."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    langchain_success_count: int | None = None


class VersionStats(BaseModel):
    """Stats for a single prompt version."""

    version: str
    total_traces: int
    avg_response_time_ms: float
    langchain_success_count: int
    success_rate: float


class CompareResponse(BaseModel):
    """Response model for version comparison."""

    version1: VersionStats
    version2: VersionStats
    response_time_diff: float
    success_rate_diff: float


@router.get("", response_model=ApiResponse[PaginatedData[TraceResponse]])
async def list_traces(
    game_id: str | None = Query(None, description="Filter by game ID"),
    experiment_id: str | None = Query(None, description="Filter by experiment ID"),
    player_id: str | None = Query(None, description="Filter by player ID"),
    model: str | None = Query(None, description="Filter by model"),
    parser_ok: bool | None = Query(
        None, description="Filter by langchain parser success (true/false)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[PaginatedData[TraceResponse]]:
    """List traces with optional AND-combined filters."""
    offset = (page - 1) * page_size
    traces, total = await service.list_traces(
        game_id=game_id,
        experiment_id=experiment_id,
        player_id=player_id,
        model=model,
        parser_ok=parser_ok,
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
    parser_ok: bool | None = Query(
        None, description="Filter by langchain parser success (true/false)"
    ),
    start_time: str | None = Query(None, description="Start time (ISO format)"),
    end_time: str | None = Query(None, description="End time (ISO format)"),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[MetricsResponse]:
    """Get aggregated metrics for traces."""
    metrics = await service.get_metrics(
        game_id=game_id,
        experiment_id=experiment_id,
        player_id=player_id,
        model=model,
        parser_ok=parser_ok,
        start_time=start_time,
        end_time=end_time,
    )
    return ApiResponse(data=MetricsResponse(**metrics))


@router.get("/compare", response_model=ApiResponse[CompareResponse])
async def compare_versions(
    version1: str = Query(..., description="First prompt version"),
    version2: str = Query(..., description="Second prompt version"),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[CompareResponse]:
    """Compare metrics between two prompt versions."""
    comparison = await service.compare_prompt_versions(version1, version2)
    return ApiResponse(data=CompareResponse(**comparison))


@router.get("/{trace_id}", response_model=ApiResponse[TraceResponse])
async def get_trace(
    trace_id: str,
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[TraceResponse]:
    """Get a single trace by ID with its spans."""
    trace = await service.get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return ApiResponse(data=TraceResponse(**trace))
