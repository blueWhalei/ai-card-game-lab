"""Tests for GameService."""

from __future__ import annotations

import pytest
from dataclasses import dataclass

from app.services.game_service import GameService


@dataclass
class MockGameAction:
    """Mock GameAction for testing."""
    player_id: str
    action_type: str
    cards: list
    target: str | None = None


@pytest.fixture
def game_service():
    """Create a minimal GameService instance for testing."""
    from unittest.mock import MagicMock

    # Create service with minimal dependencies (mocked)
    return GameService(
        engine_registry=MagicMock(),
        collector=MagicMock(),
        ai_service=None,  # Will be mocked in tests
        ai_player_service=MagicMock(),
        sqlite_path=":memory:",
        decision_service=MagicMock(),
    )


class TestGameServiceInitialization:
    """Test GameService initialization."""

    def test_service_initialization(self, game_service: GameService) -> None:
        """Test that GameService can be initialized with required dependencies."""
        assert game_service is not None

    def test_empty_states_dict(self, game_service: GameService) -> None:
        """Test that game states dict starts empty."""
        assert game_service._states == {}

    def test_empty_tasks_dict(self, game_service: GameService) -> None:
        """Test that tasks dict starts empty."""
        assert game_service._tasks == {}

    def test_empty_pause_events_dict(self, game_service: GameService) -> None:
        """Test that pause events dict starts empty."""
        assert game_service._pause_events == {}


class TestGameServiceStateManagement:
    """Test game state management methods."""

    def test_get_game_state_returns_none_for_nonexistent(self, game_service: GameService) -> None:
        """Test that get_game_state returns None for non-existent games."""
        result = game_service.get_game_state("non_existent_game_id")
        assert result is None

    def test_get_game_state_returns_state_for_existing(self, game_service: GameService) -> None:
        """Test that get_game_state returns state for existing games."""
        test_state = {"game_type": "test", "current_player": "p1"}
        game_service._states["test_game"] = test_state

        result = game_service.get_game_state("test_game")
        assert result is test_state
        assert result["current_player"] == "p1"


class TestGameServiceThinkingMap:
    """Test thinking map reading methods."""

    def test_read_thinking_map_returns_empty_for_nonexistent(self, game_service: GameService) -> None:
        """Test that _read_thinking_map_from_jsonl returns empty dict for non-existent games."""
        result = game_service._read_thinking_map_from_jsonl("non_existent_game")
        assert result == {}

    def test_read_thinking_returns_empty_for_nonexistent(self, game_service: GameService) -> None:
        """Test that _read_thinking_from_jsonl returns empty list for non-existent games."""
        result = game_service._read_thinking_from_jsonl("non_existent_game")
        assert result == []
