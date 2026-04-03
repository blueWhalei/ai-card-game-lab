"""AI player statistics API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_player_stats_service
from app.schemas.common import ApiResponse
from app.services.player_stats_service import PlayerStatsService

router = APIRouter()


@router.get("/stats")
async def get_all_players_stats(
    service: PlayerStatsService = Depends(get_player_stats_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Get statistics for all AI players."""
    stats = await service.get_all_players_stats()
    return ApiResponse(data=stats)


@router.get("/{player_id}/stats")
async def get_player_stats(
    player_id: str,
    service: PlayerStatsService = Depends(get_player_stats_service),
) -> ApiResponse[dict[str, Any]]:
    """Get statistics for a specific AI player."""
    stats = await service.get_player_stats(player_id)
    return ApiResponse(data=stats)
