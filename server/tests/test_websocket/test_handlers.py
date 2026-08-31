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
    svc.get_game_state.return_value = None
    return svc


@pytest.fixture
def engine_registry() -> MagicMock:
    return MagicMock()


class TestWebSocketHandlers:
    @pytest.mark.asyncio
    async def test_handle_game_websocket_connects_and_disconnects(
        self,
        mock_websocket: AsyncMock,
        orchestration: MagicMock,
        engine_registry: MagicMock,
    ) -> None:
        with patch("app.websocket.handlers.ws_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await handle_game_websocket(
                mock_websocket, "test_game_id", orchestration, engine_registry
            )

            mock_manager.connect.assert_called_once_with("test_game_id", mock_websocket)
            mock_manager.disconnect.assert_called_once_with("test_game_id", mock_websocket)

    @pytest.mark.asyncio
    async def test_handle_game_websocket_replies_pong(
        self,
        orchestration: MagicMock,
        engine_registry: MagicMock,
    ) -> None:
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.receive_json = AsyncMock(
            side_effect=[{"type": "ping"}, WebSocketDisconnect()]
        )
        mock_ws.send_json = AsyncMock()

        with patch("app.websocket.handlers.ws_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await handle_game_websocket(
                mock_ws, "game-ping", orchestration, engine_registry
            )

            mock_ws.send_json.assert_called_with({"type": "pong"})

    @pytest.mark.asyncio
    async def test_handle_websocket_with_connection_error(
        self,
        mock_websocket: AsyncMock,
        orchestration: MagicMock,
        engine_registry: MagicMock,
    ) -> None:
        with patch("app.websocket.handlers.ws_manager") as mock_manager:
            mock_manager.connect = AsyncMock(side_effect=ConnectionError("Failed"))

            with pytest.raises(ConnectionError):
                await handle_game_websocket(
                    mock_websocket, "test_game_id", orchestration, engine_registry
                )
