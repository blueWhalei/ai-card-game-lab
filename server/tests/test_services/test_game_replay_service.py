"""Tests for GameReplayService."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.game_replay_service import GameReplayService


@pytest.fixture
def mock_collector() -> MagicMock:
    """Create a mock JsonlWriter."""
    return MagicMock()


@pytest.fixture
def replay_service(mock_collector: MagicMock, tmp_path: Path) -> GameReplayService:
    """Create a GameReplayService instance for testing."""
    return GameReplayService(
        collector=mock_collector,
        sqlite_path=str(tmp_path / "test.db"),
    )


class TestGameReplayServiceParseJsonField:
    """Test _parse_json_field method."""

    def test_parse_valid_json_string(self, replay_service: GameReplayService) -> None:
        """Test parsing a valid JSON string."""
        result = replay_service._parse_json_field(
            '{"key": "value"}',
            "game-1",
            1,
            "prompt",
        )
        assert result == {"key": "value"}

    def test_parse_already_parsed_value(self, replay_service: GameReplayService) -> None:
        """Test passing an already parsed value."""
        result = replay_service._parse_json_field(
            ["card1", "card2"],
            "game-1",
            1,
            "cards",
        )
        assert result == ["card1", "card2"]

    def test_parse_empty_value_returns_empty_list(self, replay_service: GameReplayService) -> None:
        """Test that empty value returns empty list for array fields."""
        result = replay_service._parse_json_field(
            None,
            "game-1",
            1,
            "cards",
        )
        assert result == []

    def test_parse_empty_value_returns_empty_dict(self, replay_service: GameReplayService) -> None:
        """Test that empty value returns empty dict for non-array fields."""
        result = replay_service._parse_json_field(
            None,
            "game-1",
            1,
            "metadata",
        )
        assert result == {}

    def test_parse_invalid_json_returns_empty(self, replay_service: GameReplayService) -> None:
        """Test that invalid JSON returns empty default."""
        result = replay_service._parse_json_field(
            "not valid json",
            "game-1",
            1,
            "cards",
        )
        assert result == []


class TestGameReplayServiceReadThinkingMap:
    """Test _read_thinking_map_from_jsonl method."""

    def test_returns_empty_for_nonexistent_directory(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
    ) -> None:
        """Test returns empty dict when games directory doesn't exist."""
        mock_collector._data_dir = "/nonexistent/path"
        result = replay_service._read_thinking_map_from_jsonl("game-1")
        assert result == {}

    def test_reads_thinking_from_jsonl(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test reading thinking entries from JSONL file."""
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        jsonl_file = games_dir / "game-1.jsonl"

        records = [
            {"type": "round", "round_num": 1, "thinking": "First thought"},
            {"type": "round", "round_num": 2, "thinking": "Second thought"},
            {"type": "other", "data": "ignored"},
        ]
        with jsonl_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        mock_collector._data_dir = str(tmp_path)
        result = replay_service._read_thinking_map_from_jsonl("game-1")

        assert result == {1: "First thought", 2: "Second thought"}

    def test_handles_invalid_json(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test handles invalid JSON lines gracefully."""
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        jsonl_file = games_dir / "game-1.jsonl"

        with jsonl_file.open("w", encoding="utf-8") as f:
            f.write('{"type": "round", "round_num": 1, "thinking": "Valid"}\n')
            f.write("invalid json line\n")
            f.write('{"type": "round", "round_num": 2, "thinking": "Also valid"}\n')

        mock_collector._data_dir = str(tmp_path)
        result = replay_service._read_thinking_map_from_jsonl("game-1")

        assert result == {1: "Valid", 2: "Also valid"}


class TestGameReplayServiceReadThinkingList:
    """Test read_thinking_list_from_jsonl method."""

    def test_returns_sorted_list(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test returns thinking list sorted by round number."""
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        jsonl_file = games_dir / "game-1.jsonl"

        records = [
            {"type": "round", "round_num": 3, "thinking": "Third"},
            {"type": "round", "round_num": 1, "thinking": "First"},
            {"type": "round", "round_num": 2, "thinking": "Second"},
        ]
        with jsonl_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        mock_collector._data_dir = str(tmp_path)
        result = replay_service.read_thinking_list_from_jsonl("game-1")

        assert result == ["First", "Second", "Third"]


class TestGameReplayServiceReadThinkingListByPlayer:
    """Test read_thinking_list_by_player method."""

    def test_returns_empty_for_nonexistent_directory(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
    ) -> None:
        """Test returns empty dict when games directory doesn't exist."""
        mock_collector._data_dir = "/nonexistent/path"
        result = replay_service.read_thinking_list_by_player("game-1")
        assert result == {}

    def test_groups_by_player_id(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test grouping thinking by player_id."""
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        jsonl_file = games_dir / "game-1.jsonl"

        # Thinking must be > 50 chars to pass filter
        p1_thought_1 = "Player 1 first thinking process that is detailed enough to pass filter"
        p1_thought_2 = "Player 1 second thinking process that is detailed enough to pass filter"
        p2_thought_1 = "Player 2 first thinking process that is detailed enough to pass filter"

        records = [
            {"type": "round", "player_id": "player1", "thinking": p1_thought_1},
            {"type": "round", "player_id": "player2", "thinking": p2_thought_1},
            {"type": "round", "player_id": "player1", "thinking": p1_thought_2},
        ]
        with jsonl_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        mock_collector._data_dir = str(tmp_path)
        result = replay_service.read_thinking_list_by_player("game-1")

        assert result == {
            "player1": [p1_thought_1, p1_thought_2],
            "player2": [p2_thought_1],
        }

    def test_filters_short_thinking(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test filters out thinking shorter than 50 characters."""
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        jsonl_file = games_dir / "game-1.jsonl"

        long_thinking = "This is a long thinking content that should be included in results"
        short_thinking = "Too short"

        records = [
            {"type": "round", "player_id": "player1", "thinking": long_thinking},
            {"type": "round", "player_id": "player1", "thinking": short_thinking},
        ]
        with jsonl_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        mock_collector._data_dir = str(tmp_path)
        result = replay_service.read_thinking_list_by_player("game-1")

        assert result == {"player1": [long_thinking]}

    def test_skips_non_round_records(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test skips non-round type records."""
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        jsonl_file = games_dir / "game-1.jsonl"

        round_thinking = "This is a round record thinking that is definitely long enough to pass"
        game_start_thinking = "This is a game start thinking that is also long enough to pass"

        records = [
            {"type": "game_start", "player_id": "player1", "thinking": game_start_thinking},
            {"type": "round", "player_id": "player1", "thinking": round_thinking},
        ]
        with jsonl_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        mock_collector._data_dir = str(tmp_path)
        result = replay_service.read_thinking_list_by_player("game-1")

        assert result == {"player1": [round_thinking]}

    def test_handles_missing_player_id(
        self,
        replay_service: GameReplayService,
        mock_collector: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test handles records without player_id."""
        games_dir = tmp_path / "games"
        games_dir.mkdir()
        jsonl_file = games_dir / "game-1.jsonl"

        no_player_thinking = "This is a thinking record without player ID but long enough"
        with_player_thinking = "This is a thinking record with player ID that is long enough"

        records = [
            {"type": "round", "thinking": no_player_thinking},
            {"type": "round", "player_id": "player1", "thinking": with_player_thinking},
        ]
        with jsonl_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        mock_collector._data_dir = str(tmp_path)
        result = replay_service.read_thinking_list_by_player("game-1")

        # Only the record with player_id should be included
        assert result == {"player1": [with_player_thinking]}
