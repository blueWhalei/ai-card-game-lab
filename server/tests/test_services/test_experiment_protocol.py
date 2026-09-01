"""Experiment protocol snapshot and paired-deal collect/compare."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.experiment_repo import ExperimentRepository
from app.services.experiment_service import ExperimentService


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "protocol.db")
    await init_db(path)
    return path


def _fake_game_service() -> MagicMock:
    cfg_svc = MagicMock()
    configs = {
        "cfg_a": {
            "id": "cfg_a",
            "name": "A",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        },
        "cfg_b": {
            "id": "cfg_b",
            "name": "B",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.5,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        },
        "cfg_c": {
            "id": "cfg_c",
            "name": "C",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.9,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        },
        "cfg_lora": {
            "id": "cfg_lora",
            "name": "LoRA",
            "notes": "",
            "model_config": {
                "provider": "ollama",
                "model_name": "acgl",
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 128,
            },
        },
    }
    cfg_svc.get_config.side_effect = lambda pid: configs.get(pid)
    gs = MagicMock()
    gs.player_slots.return_value = (3, 3)
    gs._experiment_config_service = cfg_svc
    gs.create_game = AsyncMock()
    gs.start_game = AsyncMock()
    return gs


async def test_create_freezes_player_protocol(db_path: str) -> None:
    gs = _fake_game_service()
    service = ExperimentService(sqlite_path=db_path, game_service=gs)
    created = await service.create_experiment(
        name="snap",
        notes="",
        game_type="doudizhu",
        player_ids=["cfg_a", "cfg_b", "cfg_c"],
        target_games=3,
    )
    protocol = created["protocol"]
    assert protocol is not None
    assert protocol["schema_version"] == 1
    assert protocol["pair_deals"] is False
    assert protocol["deal_seeds"] == []
    assert [p["id"] for p in protocol["players"]] == ["cfg_a", "cfg_b", "cfg_c"]
    assert protocol["players"][0]["model_config"]["temperature"] == 0.7


async def test_collect_assigns_seeds_and_frozen_players(db_path: str) -> None:
    gs = _fake_game_service()
    created_games: list[dict[str, Any]] = []

    async def create_game(**kwargs: Any) -> dict[str, Any]:
        gid = f"g-{len(created_games)}"
        created_games.append(kwargs)
        return {"id": gid}

    gs.create_game = AsyncMock(side_effect=create_game)
    gs.start_game = AsyncMock(return_value={})

    service = ExperimentService(sqlite_path=db_path, game_service=gs)
    exp = await service.create_experiment(
        name="collect",
        notes="",
        game_type="doudizhu",
        player_ids=["cfg_a", "cfg_b", "cfg_c"],
        target_games=5,
    )

    async with aiosqlite.connect(db_path) as db:
        result = await service.collect(exp["id"], count=2, db=db)

    assert result["count"] == 2
    assert len(created_games) == 2
    assert created_games[0]["deal_seed"] is not None
    assert created_games[0]["paired"] is False
    assert created_games[0]["frozen_players"][0]["id"] == "cfg_a"
    assert created_games[0]["deal_seed"] != created_games[1]["deal_seed"]

    refreshed = await service.get_experiment(exp["id"], include_games=False)
    assert len(refreshed["protocol"]["deal_seeds"]) == 2
    assert refreshed["protocol"]["deal_seeds"][0] == created_games[0]["deal_seed"]


async def test_control_copies_deal_seeds(db_path: str) -> None:
    gs = _fake_game_service()
    service = ExperimentService(sqlite_path=db_path, game_service=gs)
    source = await service.create_experiment(
        name="source",
        notes="",
        game_type="doudizhu",
        player_ids=["cfg_a", "cfg_b", "cfg_c"],
        target_games=5,
    )
    now = datetime.now(tz=UTC).isoformat()
    async with aiosqlite.connect(db_path) as db:
        repo = ExperimentRepository(db)
        protocol = dict(source["protocol"])
        protocol["deal_seeds"] = [111, 222, 333]
        await repo.update_protocol(source["id"], protocol, updated_at=now)

    control = await service.create_experiment(
        name="control",
        notes="",
        game_type="doudizhu",
        player_ids=["cfg_lora", "cfg_b", "cfg_c"],
        target_games=5,
        source_experiment_id=source["id"],
        pair_deals=True,
    )
    assert control["protocol"]["pair_deals"] is True
    assert control["protocol"]["source_experiment_id"] == source["id"]
    assert control["protocol"]["deal_seeds"] == [111, 222, 333]

    created_games: list[dict[str, Any]] = []

    async def create_game(**kwargs: Any) -> dict[str, Any]:
        gid = f"cg-{len(created_games)}"
        created_games.append(kwargs)
        return {"id": gid}

    gs.create_game = AsyncMock(side_effect=create_game)
    gs.start_game = AsyncMock(return_value={})

    async with aiosqlite.connect(db_path) as db:
        await service.collect(control["id"], count=2, db=db)

    assert created_games[0]["deal_seed"] == 111
    assert created_games[0]["paired"] is True
    assert created_games[1]["deal_seed"] == 222
    assert created_games[1]["paired"] is True


async def test_compare_paired_wins(db_path: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    players_a = '["cfg_a","cfg_b","cfg_c"]'
    players_b = '["cfg_lora","cfg_b","cfg_c"]'
    protocol_a = (
        '{"schema_version":1,"deal_seeds":[10,20],"pair_deals":false,'
        '"players":[],"source_experiment_id":null,"frozen_at":"%s","prompt_version":"v1"}'
        % now
    )
    protocol_b = (
        '{"schema_version":1,"deal_seeds":[10,20],"pair_deals":true,'
        '"players":[],"source_experiment_id":"exp-a","frozen_at":"%s","prompt_version":"v1"}'
        % now
    )
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO experiments (
                id, name, notes, game_type, player_ids, target_games,
                protocol, created_at, updated_at
            ) VALUES
                ('exp-a', 'A', '', 'doudizhu', ?, 5, ?, ?, ?),
                ('exp-b', 'B', '', 'doudizhu', ?, 5, ?, ?, ?)
            """,
            (players_a, protocol_a, now, now, players_b, protocol_b, now, now),
        )
        await db.execute(
            """
            INSERT INTO games (
                id, game_type, status, player_ids, winner_id, total_rounds,
                data_file, created_at, experiment_id, metadata
            ) VALUES
                ('ga1', 'doudizhu', 'finished', ?, 'cfg_a', 10, 'a1.jsonl', ?, 'exp-a',
                 '{"deal_seed":10,"paired":false}'),
                ('ga2', 'doudizhu', 'finished', ?, 'cfg_b', 10, 'a2.jsonl', ?, 'exp-a',
                 '{"deal_seed":20,"paired":false}'),
                ('gb1', 'doudizhu', 'finished', ?, 'cfg_lora', 10, 'b1.jsonl', ?, 'exp-b',
                 '{"deal_seed":10,"paired":true}'),
                ('gb2', 'doudizhu', 'finished', ?, 'cfg_b', 10, 'b2.jsonl', ?, 'exp-b',
                 '{"deal_seed":20,"paired":true}')
            """,
            (players_a, now, players_a, now, players_b, now, players_b, now),
        )
        await db.commit()

    service = ExperimentService(sqlite_path=db_path, game_service=_fake_game_service())
    payload = await service.compare_experiments(["exp-a", "exp-b"])
    by_id = {item["id"]: item for item in payload["experiments"]}
    assert by_id["exp-a"]["paired_n"] == 2
    assert by_id["exp-b"]["paired_n"] == 2
    a_stats = {s["player_id"]: s for s in by_id["exp-a"]["player_stats"]}
    b_stats = {s["player_id"]: s for s in by_id["exp-b"]["player_stats"]}
    assert a_stats["cfg_a"]["paired_wins"] == 1
    assert a_stats["cfg_b"]["paired_wins"] == 1
    assert b_stats["cfg_lora"]["paired_wins"] == 1
    assert b_stats["cfg_b"]["paired_wins"] == 1
    assert by_id["exp-a"]["paired_seat_wins"][0] == 1
    assert by_id["exp-b"]["paired_seat_wins"][0] == 1
