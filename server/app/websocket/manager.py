"""WebSocket connection manager for real-time game observation."""

from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """Manages per-game WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        self._active: dict[str, list[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._active.setdefault(game_id, []).append(websocket)
        logger.info("ws_connected", game_id=game_id)

    async def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        connections = self._active.get(game_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._active.pop(game_id, None)
        logger.info("ws_disconnected", game_id=game_id)

    async def broadcast(self, game_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all connections observing *game_id*."""
        dead: list[WebSocket] = []
        for ws in self._active.get(game_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(game_id, ws)

    async def broadcast_trace_event(
        self,
        game_id: str,
        event_type: str,
        trace_data: dict[str, Any],
    ) -> None:
        """Broadcast a trace event to all connections observing *game_id*."""
        message = {
            "type": event_type,
            "game_id": game_id,
            "data": trace_data,
        }
        await self.broadcast(game_id, message)
        logger.info(
            "trace_event_broadcast",
            event_type=event_type,
            game_id=game_id,
        )

    def get_connection_count(self, game_id: str) -> int:
        """Return the number of active connections for a game."""
        return len(self._active.get(game_id, []))


ws_manager = ConnectionManager()
