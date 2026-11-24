"""Seat win/loss counts for experiment configurations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.database import init_db, open_db_connection
from app.repositories.experiment_config_stats_repo import ExperimentConfigStatsRepository


@pytest.mark.asyncio
async def test_team_wins_for_both_peasants(tmp_path: Path) -> None:
    db_path = str(tmp_path / "app.db")
    await init_db(db_path)
    db = await open_db_connection(db_path)
    try:
        await db.execute(
            """
            INSERT INTO games (id, game_type, status, player_ids, winner_id, winner_role, metadata, created_at, data_file)
            VALUES (?, 'doudizhu', 'finished', ?, 'aggressive_tiger', 'peasant', '{"landlord_id":"cautious_fox"}', '2026-08-28T00:00:00+00:00', 'test.jsonl')
            """,
            (
                "game_1",
                json.dumps(["aggressive_tiger", "cautious_fox", "random_panda"]),
            ),
        )
        await db.commit()
        repo = ExperimentConfigStatsRepository(db)
        assert await repo.seat_record("aggressive_tiger") == (1, 1)
        assert await repo.seat_record("random_panda") == (1, 1)
        assert await repo.seat_record("cautious_fox") == (1, 0)
        assert await repo.seat_record("missing_cfg") == (0, 0)
    finally:
        await db.close()
