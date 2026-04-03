"""WebSocket message handlers for game observation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from app.websocket.manager import ws_manager

if TYPE_CHECKING:
    from app.core.engine.registry import GameEngineRegistry
    from app.services.game_orchestration_service import GameOrchestrationService

logger = structlog.get_logger()


async def handle_game_websocket(
    websocket: WebSocket,
    game_id: str,
    orchestration_service: GameOrchestrationService,
    engine_registry: GameEngineRegistry,
) -> None:
    """Handle a game observation WebSocket connection.

    Accepts the connection, registers it with the manager, sends the
    current game state snapshot if the game is active, and processes
    incoming messages.
    """
    await ws_manager.connect(game_id, websocket)

    state = orchestration_service.get_game_state(game_id)
    if state is not None:
        try:
            engine = engine_registry.get(state.game_type)
            public_info = engine.get_public_info(state, "observer")
            await websocket.send_json({
                "type": "state_update",
                "game_id": game_id,
                "data": public_info,
            })
        except Exception:
            logger.warning("ws_state_snapshot_failed", game_id=game_id, exc_info=True)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await ws_manager.disconnect(game_id, websocket)
