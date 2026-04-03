"""Tests for WebSocket connection manager."""

from __future__ import annotations

import pytest

from app.websocket.manager import ConnectionManager, ws_manager


@pytest.fixture
def connection_manager():
    """Create a fresh ConnectionManager for each test."""
    return ConnectionManager()


class TestConnectionManagerInitialization:
    """Test ConnectionManager initialization."""

    def test_manager_initialization(self, connection_manager: ConnectionManager) -> None:
        """Test that ConnectionManager can be initialized."""
        assert connection_manager is not None
        assert connection_manager._active == {}

    def test_global_manager_singleton(self) -> None:
        """Test that global ws_manager is available."""
        assert ws_manager is not None
        assert isinstance(ws_manager, ConnectionManager)


class TestConnectionManagerConnect:
    """Test WebSocket connection management."""

    @pytest.mark.asyncio
    async def test_connect_adds_connection(self, connection_manager: ConnectionManager) -> None:
        """Test that connect adds a connection to the registry."""
        from unittest.mock import AsyncMock

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        await connection_manager.connect("game_1", mock_ws)

        assert "game_1" in connection_manager._active
        assert mock_ws in connection_manager._active["game_1"]

    @pytest.mark.asyncio
    async def test_connect_creates_game_entry(self, connection_manager: ConnectionManager) -> None:
        """Test that connect creates a new game entry if not exists."""
        from unittest.mock import AsyncMock

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        await connection_manager.connect("new_game", mock_ws)

        assert "new_game" in connection_manager._active
        assert len(connection_manager._active["new_game"]) == 1

    @pytest.mark.asyncio
    async def test_connect_appends_to_existing_game(self, connection_manager: ConnectionManager) -> None:
        """Test that connect appends to existing game entry."""
        from unittest.mock import AsyncMock

        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()

        game_id = "existing_game"
        await connection_manager.connect(game_id, mock_ws1)
        await connection_manager.connect(game_id, mock_ws2)

        assert game_id in connection_manager._active
        assert len(connection_manager._active[game_id]) == 2


class TestConnectionManagerDisconnect:
    """Test WebSocket disconnection management."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, connection_manager: ConnectionManager) -> None:
        """Test that disconnect removes a connection from the registry."""
        from unittest.mock import AsyncMock

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        game_id = "game_test"
        await connection_manager.connect(game_id, mock_ws)
        assert mock_ws in connection_manager._active[game_id]

        await connection_manager.disconnect(game_id, mock_ws)

        assert mock_ws not in connection_manager._active[game_id]

    @pytest.mark.asyncio
    async def test_disconnect_removes_game_entry_when_empty(self, connection_manager: ConnectionManager) -> None:
        """Test that disconnect removes game entry when no connections remain."""
        from unittest.mock import AsyncMock

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        game_id = "game_empty"
        await connection_manager.connect(game_id, mock_ws)

        # Disconnect the only connection
        await connection_manager.disconnect(game_id, mock_ws)

        assert game_id not in connection_manager._active

    @pytest.mark.asyncio
    async def test_disconnect_ignores_unknown_game(self, connection_manager: ConnectionManager) -> None:
        """Test that disconnect handles unknown game IDs gracefully."""
        from unittest.mock import AsyncMock

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        # Should not raise exception
        await connection_manager.disconnect("unknown_game", mock_ws)


class TestConnectionManagerBroadcast:
    """Test WebSocket broadcast functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self, connection_manager: ConnectionManager) -> None:
        """Test that broadcast sends message to all connections for a game."""
        from unittest.mock import AsyncMock

        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        game_id = "broadcast_test"
        await connection_manager.connect(game_id, mock_ws1)
        await connection_manager.connect(game_id, mock_ws2)

        test_message = {"type": "test", "data": "hello"}

        await connection_manager.broadcast(game_id, test_message)

        mock_ws1.send_json.assert_called_once_with(test_message)
        mock_ws2.send_json.assert_called_once_with(test_message)

    @pytest.mark.asyncio
    async def test_broadcast_ignores_unknown_game(self, connection_manager: ConnectionManager) -> None:
        """Test that broadcast handles unknown game IDs gracefully."""
        test_message = {"type": "test", "data": "hello"}

        # Should not raise exception
        await connection_manager.broadcast("unknown_game", test_message)

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self, connection_manager: ConnectionManager) -> None:
        """Test that broadcast removes connections that fail to send."""
        from unittest.mock import AsyncMock

        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2.send_json = AsyncMock(side_effect=Exception("Send failed"))

        game_id = "dead_conn_test"
        await connection_manager.connect(game_id, mock_ws1)
        await connection_manager.connect(game_id, mock_ws2)

        test_message = {"type": "test", "data": "hello"}

        # After broadcast, only one connection should remain
        await connection_manager.broadcast(game_id, test_message)

        assert len(connection_manager._active[game_id]) == 0


class TestConnectionManagerConnectionCount:
    """Test connection count tracking."""

    def test_get_connection_count_for_nonexistent_game(self, connection_manager: ConnectionManager) -> None:
        """Test that get_connection_count returns 0 for non-existent games."""
        count = connection_manager.get_connection_count("non_existent_game")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_connection_count_for_existing_game(self, connection_manager: ConnectionManager) -> None:
        """Test that get_connection_count returns correct count for existing games."""
        from unittest.mock import AsyncMock

        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws3.accept = AsyncMock()

        game_id = "count_test"
        await connection_manager.connect(game_id, mock_ws1)
        await connection_manager.connect(game_id, mock_ws2)
        await connection_manager.connect(game_id, mock_ws3)

        count = connection_manager.get_connection_count(game_id)
        assert count == 3


class TestConnectionManagerBroadcastTraceEvent:
    """Test trace event broadcast functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_trace_event(self, connection_manager: ConnectionManager) -> None:
        """Test that broadcast_trace_event sends properly formatted trace messages."""
        from unittest.mock import AsyncMock

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        game_id = "trace_test"
        await connection_manager.connect(game_id, mock_ws)

        trace_data = {"trace_id": "123", "round": 1}
        await connection_manager.broadcast_trace_event(game_id, "decision_made", trace_data)

        expected_message = {
            "type": "decision_made",
            "game_id": game_id,
            "data": trace_data,
        }
        mock_ws.send_json.assert_called_once_with(expected_message)
