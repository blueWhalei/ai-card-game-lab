"""Game replay service - handles game replay functionality."""

from __future__ import annotations

import asyncio
import json as json_mod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiosqlite
import structlog

from app.repositories.game_repo import GameRepository
from app.repositories.round_repo import RoundRepository
from app.utils.exceptions import GameNotFoundError

if TYPE_CHECKING:
    import aiosqlite

    from app.core.collector.jsonl_writer import JsonlWriter

logger = structlog.get_logger()


class GameReplayService:
    """Service for retrieving and assembling game replay data.

    This service is responsible for:
    - Reading game data from SQLite and JSONL files
    - Assembling complete replay data for finished games
    - Parsing and merging thinking data from JSONL
    """

    def __init__(
        self,
        collector: JsonlWriter,
        sqlite_path: str,
    ) -> None:
        self._collector = collector
        self._sqlite_path = sqlite_path

    async def get_replay_data(self, game_id: str) -> dict[str, Any]:
        """Assemble full replay data for a finished game.

        Args:
            game_id: The game identifier

        Returns:
            Dictionary containing game info, rounds, and thinking data

        Raises:
            GameNotFoundError: If the game doesn't exist
        """
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            game_repo = GameRepository(db)
            round_repo = RoundRepository(db)
            try:
                game = await game_repo.get_by_id(game_id)
            except KeyError:
                raise GameNotFoundError(game_id) from None
            rounds = await round_repo.list_by_game(game_id)

        fallback_thinking_map = self._read_thinking_map_from_jsonl(game_id)
        replay_rounds: list[dict[str, Any]] = []
        thinking_map: dict[int, str] = {}

        for round_row in rounds:
            round_num = round_row.get("round_num")
            cards_raw = round_row.get("cards")
            hand_snapshot_raw = round_row.get("hand_snapshot")
            all_hands_raw = round_row.get("all_hands")
            prompt_raw = round_row.get("prompt")
            thinking = ""
            if isinstance(round_num, int):
                thinking = fallback_thinking_map.get(round_num, "")
                if thinking:
                    thinking_map[round_num] = thinking

            cards = self._parse_json_field(cards_raw, game_id, round_num, "cards")
            hand_snapshot = self._parse_json_field(
                hand_snapshot_raw, game_id, round_num, "hand_snapshot"
            )
            all_hands = self._parse_json_field(
                all_hands_raw, game_id, round_num, "all_hands"
            )
            prompt = self._parse_json_field(prompt_raw, game_id, round_num, "prompt")

            replay_rounds.append({
                **dict(round_row),
                "cards": cards,
                "hand_snapshot": hand_snapshot,
                "all_hands": all_hands,
                "prompt": prompt,
                "thinking": thinking,
                "total_tokens": round_row.get("total_tokens"),
            })

        return {
            "game": dict(game),
            "rounds": replay_rounds,
            "thinking": thinking_map,
        }

    def _parse_json_field(
        self,
        raw_value: Any,
        game_id: str,
        round_num: int | None,
        field_name: str,
    ) -> Any:
        """Parse a JSON field with error handling.

        Args:
            raw_value: The raw value to parse
            game_id: Game ID for logging
            round_num: Round number for logging
            field_name: Field name for logging

        Returns:
            Parsed value or empty default
        """
        if not raw_value:
            return [] if field_name in ("cards", "hand_snapshot", "prompt") else {}

        try:
            return json_mod.loads(raw_value) if isinstance(raw_value, str) else raw_value
        except json_mod.JSONDecodeError as e:
            logger.warning(
                "replay_json_parse_failed",
                game_id=game_id,
                round_num=round_num,
                field=field_name,
                error=str(e),
            )
            return [] if field_name in ("cards", "hand_snapshot", "prompt") else {}

    def _read_thinking_map_from_jsonl(self, game_id: str) -> dict[int, str]:
        """Read thinking texts keyed by round number from a game's JSONL file.

        Args:
            game_id: The game identifier

        Returns:
            Dictionary mapping round numbers to thinking text
        """
        data_dir = Path(self._collector.data_dir)
        thinking_map: dict[int, str] = {}
        games_dir = data_dir / "games"
        if not games_dir.exists():
            return thinking_map
        for jsonl_file in games_dir.rglob(f"{game_id}.jsonl"):
            with jsonl_file.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json_mod.loads(line)
                    except json_mod.JSONDecodeError as e:
                        logger.warning(
                            "jsonl_parse_failed",
                            game_id=game_id,
                            file_path=str(jsonl_file),
                            error=str(e),
                        )
                        continue
                    if record.get("type") != "round":
                        continue
                    round_num = record.get("round_num")
                    thinking = record.get("thinking")
                    if isinstance(round_num, int) and thinking:
                        thinking_map[round_num] = thinking
            break
        return thinking_map

    async def read_thinking_map_from_jsonl(self, game_id: str) -> dict[int, str]:
        """Read thinking texts keyed by round number from a game's JSONL file.

        Args:
            game_id: The game identifier

        Returns:
            Dictionary mapping round numbers to thinking text
        """
        return await asyncio.to_thread(self._read_thinking_map_from_jsonl, game_id)

    def read_thinking_list_from_jsonl(self, game_id: str) -> list[str]:
        """Read all thinking texts from a game's JSONL file.

        Args:
            game_id: The game identifier

        Returns:
            List of thinking texts sorted by round number
        """
        thinking_map = self._read_thinking_map_from_jsonl(game_id)
        return [thinking_map[key] for key in sorted(thinking_map)]

    def read_thinking_list_by_player(
        self, game_id: str
    ) -> dict[str, list[str]]:
        """Read thinking texts grouped by player_id from a game's JSONL file.

        Args:
            game_id: The game identifier

        Returns:
            Dictionary mapping player_id to list of thinking texts
        """
        data_dir = Path(self._collector.data_dir)
        player_thinking: dict[str, list[str]] = {}
        games_dir = data_dir / "games"
        if not games_dir.exists():
            return player_thinking

        for jsonl_file in games_dir.rglob(f"{game_id}.jsonl"):
            with jsonl_file.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json_mod.loads(line)
                    except json_mod.JSONDecodeError as e:
                        logger.warning(
                            "jsonl_parse_failed",
                            game_id=game_id,
                            file_path=str(jsonl_file),
                            error=str(e),
                        )
                        continue
                    if record.get("type") != "round":
                        continue
                    player_id = record.get("player_id")
                    thinking = record.get("thinking")
                    if player_id and thinking and len(thinking) > 50:
                        if player_id not in player_thinking:
                            player_thinking[player_id] = []
                        player_thinking[player_id].append(thinking)
            break

        return player_thinking
