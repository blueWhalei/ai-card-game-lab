"""Tests for zero-key demo game + verdict experiment seeding."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

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
from app.services.experiment_service import ExperimentService

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
        assert ctl_1["winner_role"] == "peasant"
        main_meta = main_1.get("metadata") or {}
        ctl_meta = ctl_1.get("metadata") or {}
        if isinstance(main_meta, str):
            main_meta = json.loads(main_meta)
        if isinstance(ctl_meta, str):
            ctl_meta = json.loads(ctl_meta)
        assert main_meta.get("deal_seed") == 1001
        assert ctl_meta.get("deal_seed") == 1001


async def test_seeded_report_citations_open_the_same_pair_step(
    seed_service: DemoSeedService,
) -> None:
    await seed_service.seed_demo()
    service = ExperimentService(sqlite_path=seed_service.sqlite_path, game_service=MagicMock())
    comparison = await service.save_comparison(
        [DEMO_EXPERIMENT_ID, DEMO_CONTROL_ID], "Demo report", []
    )
    pair = await service.research_pair(comparison["id"], 1001)
    assert [frame["turn"] for frame in pair["frames"]] == list(range(5))
    for frame in pair["frames"]:
        assert frame["left"] is not None
        assert frame["right"] is not None
        assert frame["left"]["round_number"] == frame["turn"]
        assert frame["right"]["round_number"] == frame["turn"]
    cited = pair["frames"][-1]["left"]
    revision = await service.save_research(
        comparison["id"],
        0,
        "Synthetic records only",
        "",
        "Not model performance evidence",
        [{"decision_id": cited["id"], "note": "Last recorded step"}],
    )
    report = await service.get_research(revision["record"]["id"], export=True)
    assert report["record"]["evidence"][0]["decision"]["round_number"] == 4
