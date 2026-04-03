"""AI player statistics service."""

from __future__ import annotations

from typing import Any

import aiosqlite
import structlog

from app.repositories.player_stats_repo import PlayerStatsRepository

logger = structlog.get_logger()


class PlayerStatsService:
    """Business logic for AI player statistics."""

    def __init__(self, sqlite_path: str) -> None:
        self._sqlite_path = sqlite_path

    async def get_all_players_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all AI players."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = PlayerStatsRepository(db)
            player_ids = await repo.get_all_player_ids()

            stats = []
            for player_id in player_ids:
                stat = await self._build_player_stats(repo, player_id)
                stats.append(stat)

        stats.sort(key=lambda x: x["games_played"], reverse=True)
        return stats

    async def get_player_stats(self, player_id: str) -> dict[str, Any]:
        """Get statistics for a specific AI player."""
        async with aiosqlite.connect(self._sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            repo = PlayerStatsRepository(db)
            return await self._build_player_stats(repo, player_id, include_last_game_id=True)

    async def _build_player_stats(
        self,
        repo: PlayerStatsRepository,
        player_id: str,
        *,
        include_last_game_id: bool = False,
    ) -> dict[str, Any]:
        """Build stats dict for a single player."""
        games_played = await repo.count_games_played(player_id)
        wins = await repo.count_wins(player_id)
        last_game = await repo.get_last_game(player_id)

        result: dict[str, Any] = {
            "player_id": player_id,
            "games_played": games_played,
            "wins": wins,
            "losses": games_played - wins,
            "win_rate": wins / games_played if games_played > 0 else 0.0,
            "last_game_at": last_game["created_at"] if last_game else None,
        }

        if include_last_game_id:
            result["last_game_id"] = last_game["id"] if last_game else None

        return result
