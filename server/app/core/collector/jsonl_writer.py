"""JSONL file writer for game data archival."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class JsonlWriter:
    """Writes game records as newline-delimited JSON to per-game files.

    File layout::

        {data_dir}/games/{YYYY-MM-DD}/{game_id}.jsonl
    """

    def __init__(self, data_dir: str) -> None:
        self._data_dir = Path(data_dir)

    @property
    def data_dir(self) -> Path:
        """Public read-only access to the data directory."""
        return self._data_dir

    def _game_file_path(self, game_id: str) -> Path:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        directory = self._data_dir / "games" / today
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{game_id}.jsonl"

    def _write_line(self, game_id: str, record: dict[str, Any]) -> None:
        path = self._game_file_path(game_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def start_game(
        self,
        game_id: str,
        game_type: str,
        player_ids: list[str],
    ) -> str:
        """Write the game_start record and return the relative file path."""
        record = {
            "type": "game_start",
            "game_id": game_id,
            "game_type": game_type,
            "players": player_ids,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._write_line(game_id, record)
        path = self._game_file_path(game_id)
        logger.info("jsonl_game_started", game_id=game_id, path=str(path))
        return str(path.relative_to(self._data_dir))

    def record_round(self, game_id: str, data: dict[str, Any]) -> None:
        """Append a round record to the game's JSONL file."""
        data["type"] = "round"
        data["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        self._write_line(game_id, data)

    def end_game(self, game_id: str, summary: dict[str, Any]) -> None:
        """Write the game_end record."""
        record = {
            "type": "game_end",
            "game_id": game_id,
            **summary,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._write_line(game_id, record)
        logger.info("jsonl_game_ended", game_id=game_id)
