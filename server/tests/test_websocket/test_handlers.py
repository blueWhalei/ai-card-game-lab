"""Tests for WebSocket handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from app.websocket.handlers import handle_game_websocket


@pytest.fixture
def mock_websocket() -> AsyncMock:
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock(side_effect=WebSocketDisconnect())
    return ws


@pytest.fixture
def orchestration() -> MagicMock:
    svc = MagicMock()
    svc.observer_snapshot.return_value = None
    return svc


class TestWebSocketHandlers:
    @pytest.mark.asyncio
    async def test_handle_game_websocket_connects_and_disconnects(
        self,
        mock_websocket: AsyncMock,
        orchestration: MagicMock,
    ) -> None:
        with patch("app.websocket.handlers.ws_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await handle_game_websocket(mock_websocket, "test_game_id", orchestration)

            mock_manager.connect.assert_called_once_with("test_game_id", mock_websocket)
            mock_manager.disconnect.assert_called_once_with("test_game_id", mock_websocket)

    @pytest.mark.asyncio
    async def test_handle_game_websocket_replies_pong(
        self,
        orchestration: MagicMock,
    ) -> None:
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.receive_json = AsyncMock(side_effect=[{"type": "ping"}, WebSocketDisconnect()])
        mock_ws.send_json = AsyncMock()

        with patch("app.websocket.handlers.ws_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await handle_game_websocket(mock_ws, "game-ping", orchestration)

            mock_ws.send_json.assert_called_with({"type": "pong"})

    @pytest.mark.asyncio
    async def test_handle_websocket_with_connection_error(
        self,
        mock_websocket: AsyncMock,
        orchestration: MagicMock,
    ) -> None:
        with patch("app.websocket.handlers.ws_manager") as mock_manager:
            mock_manager.connect = AsyncMock(side_effect=ConnectionError("Failed"))

            with pytest.raises(ConnectionError):
                await handle_game_websocket(mock_websocket, "test_game_id", orchestration)

    @pytest.mark.asyncio
    async def test_handle_game_websocket_sends_observer_snapshot(
        self,
        orchestration: MagicMock,
    ) -> None:
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.receive_json = AsyncMock(side_effect=WebSocketDisconnect())
        mock_ws.send_json = AsyncMock()
        orchestration.observer_snapshot.return_value = {"game_type": "doudizhu"}

        with patch("app.websocket.handlers.ws_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await handle_game_websocket(mock_ws, "game-snap", orchestration)

            mock_ws.send_json.assert_called_once_with(
                {
                    "type": "state_update",
                    "game_id": "game-snap",
                    "data": {"game_type": "doudizhu"},
                }
            )
