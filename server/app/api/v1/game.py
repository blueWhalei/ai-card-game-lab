"""Game management API endpoints."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, Query, WebSocket

from app.dependencies import (
    get_db,
    get_engine_registry,
    get_game_orchestration_service,
    get_game_service,
)
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.game import BatchCreateRequest, CreateGameRequest
from app.services.game_orchestration_service import GameOrchestrationService
from app.services.game_service import GameService
from app.websocket.handlers import handle_game_websocket

router = APIRouter()


def _normalize_game(row: dict[str, Any]) -> dict[str, Any]:
    """Ensure player_ids is always a list in the response."""
    if isinstance(row.get("player_ids"), str):
        row["player_ids"] = json.loads(row["player_ids"])
    if isinstance(row.get("metadata"), str):
        row["metadata"] = json.loads(row["metadata"])
    return row


@router.get("")
async def list_games(
    game_type: str | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    service: GameService = Depends(get_game_service),
) -> ApiResponse[PaginatedData[dict[str, Any]]]:
    items, total = await service.list_games(
        game_type=game_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        data=PaginatedData(
            items=[_normalize_game(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", status_code=201)
async def create_game(
    body: CreateGameRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: GameService = Depends(get_game_service),
) -> ApiResponse[dict[str, Any]]:
    game = await service.create_game(
        game_type=body.game_type,
        player_ids=body.player_ids,
        mode=body.mode,
        db=db,
    )
    return ApiResponse(data=_normalize_game(game))


@router.get("/{game_id}")
async def get_game(
    game_id: str,
    service: GameService = Depends(get_game_service),
) -> ApiResponse[dict[str, Any]]:
    game = await service.get_game(game_id)
    return ApiResponse(data=_normalize_game(game))


@router.post("/{game_id}/start")
async def start_game(
    game_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    service: GameService = Depends(get_game_service),
) -> ApiResponse[dict[str, Any]]:
    game = await service.start_game(game_id, db=db)
    return ApiResponse(data=_normalize_game(game))


@router.post("/{game_id}/pause")
async def pause_game(
    game_id: str,
    service: GameService = Depends(get_game_service),
) -> ApiResponse[dict[str, str]]:
    await service.pause_game(game_id)
    return ApiResponse(data={"status": "paused"})


@router.post("/{game_id}/resume")
async def resume_game(
    game_id: str,
    service: GameService = Depends(get_game_service),
) -> ApiResponse[dict[str, str]]:
    await service.resume_game(game_id)
    return ApiResponse(data={"status": "running"})


@router.get("/{game_id}/replay")
async def get_replay(
    game_id: str,
    service: GameService = Depends(get_game_service),
) -> ApiResponse[dict[str, Any]]:
    """Return full replay data for a finished game."""
    data = await service.get_replay_data(game_id)
    game = data["game"]
    if isinstance(game.get("player_ids"), str):
        game["player_ids"] = json.loads(game["player_ids"])
    return ApiResponse(data=data)


@router.get("/{game_id}/rounds")
async def get_game_rounds(
    game_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    service: GameService = Depends(get_game_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return all rounds for a game (works for running and finished games)."""
    rows = await service.get_game_rounds(game_id, db=db)
    for row in rows:
        for field in ("cards", "hand_snapshot", "prompt"):
            if isinstance(row.get(field), str):
                row[field] = json.loads(row[field])
    return ApiResponse(data=rows)


@router.post("/batch", status_code=201)
async def batch_create(
    body: BatchCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
    service: GameService = Depends(get_game_service),
) -> ApiResponse[dict[str, Any]]:
    """Create and start multiple games at once."""
    game_ids: list[str] = []
    for _ in range(body.count):
        game = await service.create_game(
            game_type=body.game_type,
            player_ids=body.player_ids,
            mode="batch",
            db=db,
        )
        await service.start_game(game["id"], db=db)
        game_ids.append(game["id"])
    return ApiResponse(data={"game_ids": game_ids, "count": len(game_ids)})


@router.websocket("/ws/{game_id}")
async def game_websocket(
    websocket: WebSocket,
    game_id: str,
    orchestration: GameOrchestrationService = Depends(get_game_orchestration_service),
    registry=Depends(get_engine_registry),
) -> None:
    await handle_game_websocket(websocket, game_id, orchestration, registry)
