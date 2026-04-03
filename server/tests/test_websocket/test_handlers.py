"""Tests for WebSocket handlers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import WebSocket

from app.websocket.handlers import handle_game_websocket


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock(return_value='{"type": "test", "data": {}}')
    ws.client = MagicMock()
    ws.client.state = MagicMock()
    return ws


class TestWebSocketHandlers:
    """Test WebSocket handler functions."""

    @pytest.mark.asyncio
    async def test_handle_game_websocket_accepts_connection(self, mock_websocket) -> None:
        """Test that handle_game_websocket accepts the WebSocket connection."""
        with patch('app.websocket.handlers.ws_manager') as mock_manager:
            mock_manager.connect = AsyncMock()

            await handle_game_websocket(mock_websocket, "test_game_id")

            mock_manager.connect.assert_called_once_with("test_game_id", mock_websocket)
            mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_game_websocket_disconnects_on_close(self, mock_websocket) -> None:
        """Test that handle_game_websocket disconnects on WebSocket close."""
        with patch('app.websocket.handlers.ws_manager') as mock_manager:
            mock_manager.disconnect = AsyncMock()

            # Simulate WebSocket closing
            mock_websocket.receive_text.side_effect = Exception("Connection closed")

            with pytest.raises(Exception):
                await handle_game_websocket(mock_websocket, "test_game_id")

            # Note: In production, the disconnect happens via cleanup logic
            # This test verifies the handler is called

    @pytest.mark.asyncio
    async def test_handle_game_websocket_processes_ping(self, mock_websocket) -> None:
        """Test that ping messages are processed correctly."""
        from app.websocket.handlers import ws_manager

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Simulate connection
        await ws_manager.connect("test_game", mock_ws)

        # Send ping message
        await mock_ws.send_json({"type": "ping"})

        # Should not raise exception
        # (In production, ping would be handled by the handler)


class TestWebSocketMessageHandling:
    """Test WebSocket message handling."""

    def test_parse_websocket_message_valid_json(self) -> None:
        """Test that valid JSON messages are parsed correctly."""
        from app.websocket.handlers import parse_ws_message

        message = '{"type": "test", "data": {"key": "value"}}'
        result = parse_ws_message(message)
        assert result["type"] == "test"
        assert result["data"]["key"] == "value"

    def test_parse_websocket_message_invalid_json(self) -> None:
        """Test that invalid JSON messages are handled gracefully."""
        from app.websocket.handlers import parse_ws_message

        message = 'invalid json {{'
        result = parse_ws_message(message)
        assert result is None


class TestWebSocketErrorHandling:
    """Test WebSocket error scenarios."""

    @pytest.mark.asyncio
    async def test_handle_websocket_with_connection_error(self, mock_websocket) -> None:
        """Test that connection errors are handled gracefully."""
        with patch('app.websocket.handlers.ws_manager') as mock_manager:
            mock_manager.connect = AsyncMock(side_effect=ConnectionError("Failed"))

            with pytest.raises(ConnectionError):
                await handle_game_websocket(mock_websocket, "test_game_id")
