"""Tests for zero-key demo game + verdict experiment seeding."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.experiment_config_repo import ExperimentConfigRepository
from app.repositories.game_repo import GameRepository
from app.services.demo_seed_service import (
    DEMO_CONTROL_ID,
    DEMO_EXPERIMENT_ID,
    DEMO_GAME_ID,
    DEMO_PLAYERS,
    DemoSeedService,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
async def seed_service(tmp_path: Path) -> DemoSeedService:
    sqlite_path = str(tmp_path / "demo.db")
    await init_db(sqlite_path)
    return DemoSeedService(sqlite_path=sqlite_path, data_dir=str(tmp_path))


async def test_seed_demo_creates_finished_game(seed_service: DemoSeedService) -> None:
    result = await seed_service.seed_demo()
    assert result["created"] is True
    assert result["game_id"] == DEMO_GAME_ID
    assert result["experiment_id"] == DEMO_EXPERIMENT_ID

    async with aiosqlite.connect(seed_service.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        game = await GameRepository(db).get_by_id(DEMO_GAME_ID)
    assert game["status"] == "finished"
    assert game["winner_role"] == "landlord"


async def test_seed_demo_is_idempotent(seed_service: DemoSeedService) -> None:
    first = await seed_service.seed_demo()
    second = await seed_service.seed_demo()
    assert first["created"] is True
    assert second["created"] is False
    assert second["game_id"] == DEMO_GAME_ID
    assert second["experiment_id"] == DEMO_EXPERIMENT_ID


async def test_seed_demo_creates_players_and_control_pair(
    seed_service: DemoSeedService,
) -> None:
    import json

    await seed_service.seed_demo()

    async with aiosqlite.connect(seed_service.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cfg_repo = ExperimentConfigRepository(db)
        for pid in DEMO_PLAYERS:
            row = await cfg_repo.get(pid)
            assert row is not None
            assert row["policy_kind"] == "heuristic"

        game_repo = GameRepository(db)
        main_1 = await game_repo.get_by_id("game_demo_main_1")
        ctl_1 = await game_repo.get_by_id("game_demo_ctl_1")
        assert main_1["experiment_id"] == DEMO_EXPERIMENT_ID
        assert ctl_1["experiment_id"] == DEMO_CONTROL_ID
        assert main_1["winner_role"] == "landlord"
        assert ctl_1["winner_role"] == "farmer"
        main_meta = main_1.get("metadata") or {}
        ctl_meta = ctl_1.get("metadata") or {}
        if isinstance(main_meta, str):
            main_meta = json.loads(main_meta)
        if isinstance(ctl_meta, str):
            ctl_meta = json.loads(ctl_meta)
        assert main_meta.get("deal_seed") == 1001
        assert ctl_meta.get("deal_seed") == 1001
