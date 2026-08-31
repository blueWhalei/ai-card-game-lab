"""Tests for zero-key demo game seeding."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from pathlib import Path
import pytest

from app.database import init_db
from app.repositories.game_repo import GameRepository
from app.services.demo_seed_service import DEMO_GAME_ID, DemoSeedService


@pytest.fixture
async def seed_service(tmp_path: Path) -> DemoSeedService:
    sqlite_path = str(tmp_path / "demo.db")
    await init_db(sqlite_path)
    return DemoSeedService(sqlite_path=sqlite_path, data_dir=str(tmp_path))


async def test_seed_demo_creates_finished_game(seed_service: DemoSeedService) -> None:
    result = await seed_service.seed_demo()
    assert result["created"] is True
    assert result["game_id"] == DEMO_GAME_ID

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
