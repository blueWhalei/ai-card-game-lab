"""Experiment config statistics service."""

from __future__ import annotations

from typing import Any

from app.database import connect_sqlite
from app.repositories.experiment_config_stats_repo import ExperimentConfigStatsRepository


class ExperimentConfigStatsService:
    """Business logic for experiment config statistics."""

    def __init__(self, sqlite_path: str) -> None:
        self._sqlite_path = sqlite_path

    async def get_all_stats(self, config_ids: list[str]) -> list[dict[str, Any]]:
        """Get statistics for the provided experiment config IDs."""
        async with connect_sqlite(self._sqlite_path) as db:
            repo = ExperimentConfigStatsRepository(db)

            stats: list[dict[str, Any]] = []
            for config_id in config_ids:
                stat = await self._build_config_stats(
                    repo,
                    config_id,
                    include_last_game_id=True,
                )
                stats.append(stat)

        stats.sort(key=lambda x: x["games_played"], reverse=True)
        return stats

    async def _build_config_stats(
        self,
        repo: ExperimentConfigStatsRepository,
        config_id: str,
        *,
        include_last_game_id: bool = False,
    ) -> dict[str, Any]:
        """Build stats dict for a single experiment config."""
        games_played = await repo.count_games_played(config_id)
        wins = await repo.count_wins(config_id)
        last_game = await repo.get_last_game(config_id)

        result: dict[str, Any] = {
            "config_id": config_id,
            "games_played": games_played,
            "wins": wins,
            "losses": games_played - wins,
            "win_rate": wins / games_played if games_played > 0 else 0.0,
            "last_game_at": last_game["created_at"] if last_game else None,
        }

        if include_last_game_id:
            result["last_game_id"] = last_game["id"] if last_game else None

        return result
