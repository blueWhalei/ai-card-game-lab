"""Round data access layer (SQLite)."""

import json
from typing import Any

import aiosqlite


class RoundRepository:
    """CRUD operations for the ``rounds`` table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, data: dict[str, Any]) -> int:
        """Insert a round record and return the auto-increment ID."""
        cursor = await self._db.execute(
            """
            INSERT INTO rounds
                (game_id, round_num, player_id, action_type,
                 cards, hand_snapshot, all_hands, prompt, raw_response,
                 prompt_tokens, completion_tokens, total_tokens, response_time_ms,
                 model_provider, model_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["game_id"],
                data["round_num"],
                data["player_id"],
                data["action_type"],
                json.dumps(data.get("cards", []), ensure_ascii=False),
                json.dumps(data.get("hand_snapshot", []), ensure_ascii=False),
                json.dumps(data.get("all_hands", {}), ensure_ascii=False),
                json.dumps(data.get("prompt", []), ensure_ascii=False),
                data.get("raw_response"),
                data.get("prompt_tokens"),
                data.get("completion_tokens"),
                data.get("total_tokens"),
                data.get("response_time_ms"),
                data.get("model_provider"),
                data.get("model_name"),
                data["created_at"],
            ),
        )
        await self._db.commit()
        return cursor.lastrowid or 0

    async def list_by_game(self, game_id: str) -> list[dict[str, Any]]:
        """Return all rounds for a given game, ordered by round_num."""
        cursor = await self._db.execute(
            "SELECT * FROM rounds WHERE game_id = ? ORDER BY round_num",
            (game_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
