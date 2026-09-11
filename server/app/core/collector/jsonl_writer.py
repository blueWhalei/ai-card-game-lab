"""JSONL file writer for game data archival."""

import json
from datetime import UTC, datetime
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
        self._paths: dict[str, Path] = {}

    @property
    def data_dir(self) -> Path:
        """Public read-only access to the data directory."""
        return self._data_dir

    def _game_file_path(self, game_id: str) -> Path:
        if game_id in self._paths:
            return self._paths[game_id]
        # A new writer (e.g. after restart) reuses an existing game's first file.
        existing = sorted((self._data_dir / "games").glob(f"*/{game_id}.jsonl"))
        if existing:
            self._paths[game_id] = existing[0]
            return existing[0]
        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        directory = self._data_dir / "games" / today
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{game_id}.jsonl"
        self._paths[game_id] = path
        return path

    def bind_game_file(self, game_id: str, data_file: str) -> None:
        """Restore the path persisted at creation, including across UTC midnight."""
        path = (self._data_dir / data_file).resolve()
        if not path.is_relative_to((self._data_dir / "games").resolve()):
            raise ValueError("Game file must stay inside the games directory")
        if path.name != f"{game_id}.jsonl":
            raise ValueError("Game file does not match game id")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._paths[game_id] = path

    def release_game(self, game_id: str) -> None:
        self._paths.pop(game_id, None)

    def prepare_game_file(self, game_id: str) -> str:
        """Choose a stable path without writing records before a reservation commits."""
        return str(self._game_file_path(game_id).relative_to(self._data_dir))

    def ensure_started(self, game_id: str, game_type: str, player_ids: list[str]) -> None:
        if not self._game_file_path(game_id).exists():
            self.start_game(game_id, game_type, player_ids)

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
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        self._write_line(game_id, record)
        path = self._game_file_path(game_id)
        logger.info("jsonl_game_started", game_id=game_id, path=str(path))
        return str(path.relative_to(self._data_dir))

    def record_round(self, game_id: str, data: dict[str, Any]) -> None:
        """Append a round record to the game's JSONL file."""
        self._write_line(
            game_id, {**data, "type": "round", "timestamp": datetime.now(tz=UTC).isoformat()}
        )

    def end_game(self, game_id: str, summary: dict[str, Any]) -> None:
        """Write the game_end record."""
        record = {
            "type": "game_end",
            "game_id": game_id,
            **summary,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        self._write_line(game_id, record)
        self.release_game(game_id)
        logger.info("jsonl_game_ended", game_id=game_id)
