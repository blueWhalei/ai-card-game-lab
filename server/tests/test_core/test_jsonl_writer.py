"""Per-game paths stay stable across days and writer instances."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.collector.jsonl_writer import JsonlWriter
from app.services.game_replay_service import GameReplayService


def test_midnight_keeps_one_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clock = MagicMock()
    clock.now.return_value = datetime(2026, 9, 11, 23, 59, tzinfo=UTC)
    monkeypatch.setattr("app.core.collector.jsonl_writer.datetime", clock)
    writer = JsonlWriter(str(tmp_path))
    relative = writer.start_game("game_test", "doudizhu", ["a", "b", "c"])
    clock.now.return_value = datetime(2026, 9, 12, 0, 1, tzinfo=UTC)
    data = {"round_num": 1, "thinking": "test"}
    writer.record_round("game_test", data)
    assert "type" not in data
    writer.end_game("game_test", {})
    files = list(tmp_path.rglob("*.jsonl"))
    assert files == [tmp_path / relative]
    assert len(files[0].read_text(encoding="utf-8").splitlines()) == 3
    assert writer._paths == {}


def test_new_writer_reuses_persisted_path(tmp_path: Path) -> None:
    relative = "games/2020-01-01/game_test.jsonl"
    writer = JsonlWriter(str(tmp_path))
    writer.bind_game_file("game_test", relative)
    writer.record_round("game_test", {"round_num": 1})
    replacement = JsonlWriter(str(tmp_path))
    replacement.record_round("game_test", {"round_num": 2})
    assert list(tmp_path.rglob("*.jsonl")) == [tmp_path / relative]
    assert len((tmp_path / relative).read_text(encoding="utf-8").splitlines()) == 2


def test_legacy_split_replay_merges_days(tmp_path: Path) -> None:
    for day, number in (("2020-01-01", 1), ("2020-01-02", 2)):
        writer = JsonlWriter(str(tmp_path))
        writer.bind_game_file("game_test", f"games/{day}/game_test.jsonl")
        writer.record_round(
            "game_test", {"round_num": number, "thinking": str(number) * 60, "player_id": "p"}
        )
    service = GameReplayService(collector=writer, sqlite_path=str(tmp_path / "unused.db"))
    assert set(service._read_thinking_map_from_jsonl("game_test")) == {1, 2}
    assert len(service.read_thinking_list_by_player("game_test")["p"]) == 2
