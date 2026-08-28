"""AI player management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from app.dependencies import get_ai_player_service
from app.schemas.ai_player import CreateAIPlayerRequest, UpdateAIPlayerRequest
from app.schemas.common import ApiResponse
from app.services.ai_player_service import AIPlayerService
from app.utils.exceptions import AppError

router = APIRouter()


class AIPlayerNotFoundError(AppError):
    def __init__(self, player_id: str) -> None:
        super().__init__(
            message=f"AI player not found: {player_id}",
            code="AI_PLAYER_NOT_FOUND",
            status_code=404,
        )


class AIPlayerConflictError(AppError):
    def __init__(self, player_id: str) -> None:
        super().__init__(
            message=f"AI player already exists: {player_id}",
            code="AI_PLAYER_CONFLICT",
            status_code=409,
        )


@router.get("")
async def list_ai_players(
    service: AIPlayerService = Depends(get_ai_player_service),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=service.list_players())


@router.post("", status_code=201)
async def create_ai_player(
    body: CreateAIPlayerRequest,
    service: AIPlayerService = Depends(get_ai_player_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        player = await service.create_player({
            "id": body.id,
            "name": body.name,
            "description": body.description,
            "avatar": body.avatar,
            "model_config": body.model_config_data.model_dump(),
        })
    except ValueError as e:
        raise AIPlayerConflictError(body.id) from e
    return ApiResponse(data=player)


@router.get("/{player_id}")
async def get_ai_player(
    player_id: str,
    service: AIPlayerService = Depends(get_ai_player_service),
) -> ApiResponse[dict[str, Any]]:
    player = service.get_player(player_id)
    if not player:
        raise AIPlayerNotFoundError(player_id)
    return ApiResponse(data=player)


@router.put("/{player_id}")
async def update_ai_player(
    player_id: str,
    body: UpdateAIPlayerRequest,
    service: AIPlayerService = Depends(get_ai_player_service),
) -> ApiResponse[dict[str, Any]]:
    update_data: dict[str, Any] = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.description is not None:
        update_data["description"] = body.description
    if body.avatar is not None:
        update_data["avatar"] = body.avatar
    if body.model_config_data is not None:
        update_data["model_config"] = body.model_config_data.model_dump()

    try:
        player = await service.update_player(player_id, update_data)
    except KeyError as e:
        raise AIPlayerNotFoundError(player_id) from e
    return ApiResponse(data=player)


@router.delete("/{player_id}", status_code=204, response_class=Response)
async def delete_ai_player(
    player_id: str,
    service: AIPlayerService = Depends(get_ai_player_service),
) -> Response:
    try:
        await service.delete_player(player_id)
    except KeyError as e:
        raise AIPlayerNotFoundError(player_id) from e
    return Response(status_code=204)
