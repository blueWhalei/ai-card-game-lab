"""Experiment configs persist to SQLite and seed from YAML when empty."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.database import init_db, open_db_connection
from app.services.experiment_config_service import ExperimentConfigService


@pytest.mark.asyncio
async def test_experiment_configs_seed_and_crud(tmp_path: Path) -> None:
    db_path = str(tmp_path / "app.db")
    yaml_path = tmp_path / "experiment_configs.yaml"
    yaml_path.write_text(
        yaml.dump(
            {
                "configs": [
                    {
                        "id": "cfg_temp_09",
                        "name": "Temp 0.9",
                        "notes": "seed note",
                        "model_config": {
                            "provider": "ollama",
                            "model_name": "llama",
                            "temperature": 0.9,
                            "top_p": 0.95,
                            "max_tokens": 128,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    await init_db(db_path)
    svc = ExperimentConfigService(db_path, str(yaml_path))
    await svc.initialize()

    configs = svc.list_configs()
    assert len(configs) == 1
    assert configs[0]["id"] == "cfg_temp_09"
    assert configs[0]["notes"] == "seed note"
    assert "avatar" not in configs[0]

    created = await svc.create_config(
        {
            "id": "cfg_b",
            "name": "B",
            "notes": "",
            "model_config": {"provider": "openai", "model_name": "gpt"},
        }
    )
    assert created["id"] == "cfg_b"

    svc2 = ExperimentConfigService(db_path, str(yaml_path))
    await svc2.initialize()
    assert len(svc2.list_configs()) == 2
    await svc2.delete_config("cfg_temp_09")
    assert svc2.get_config("cfg_temp_09") is None


@pytest.mark.asyncio
async def test_migrate_retired_deepseek_models(tmp_path: Path) -> None:
    db_path = str(tmp_path / "app.db")
    await init_db(db_path)
    svc = ExperimentConfigService(db_path, yaml_seed_path=None)
    from app.repositories.experiment_config_repo import ExperimentConfigRepository

    db = await open_db_connection(db_path)
    try:
        repo = ExperimentConfigRepository(db)
        await repo.upsert(
            {
                "id": "legacy",
                "name": "Legacy",
                "model_config": {
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "temperature": 0.7,
                },
            }
        )
    finally:
        await db.close()

    await svc.initialize()
    config = svc.get_config("legacy")
    assert config is not None
    assert config["model_config"]["model_name"] == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_migrate_ai_players_to_experiment_configs(tmp_path: Path) -> None:
    """Legacy ai_players rows migrate to experiment_configs with notes, no avatar."""
    db_path = str(tmp_path / "app.db")
    db_dir = tmp_path
    db_dir.mkdir(parents=True, exist_ok=True)

    import aiosqlite

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE ai_players (
                id            TEXT PRIMARY KEY,
                name          TEXT    NOT NULL,
                description   TEXT    NOT NULL DEFAULT '',
                avatar        TEXT    NOT NULL DEFAULT '',
                model_config  TEXT    NOT NULL,
                created_at    TEXT    NOT NULL,
                updated_at    TEXT    NOT NULL
            )
            """
        )
        model_cfg = json.dumps(
            {
                "provider": "deepseek",
                "model_name": "deepseek-v4-flash",
                "temperature": 0.8,
            },
            ensure_ascii=False,
        )
        await db.execute(
            """
            INSERT INTO ai_players (id, name, description, avatar, model_config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cfg_legacy",
                "Legacy Player",
                "migrated note",
                "avatar.png",
                model_cfg,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        await db.commit()

    await init_db(db_path)

    db = await open_db_connection(db_path)
    try:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_players'"
        )
        assert await cur.fetchone() is None

        cur = await db.execute("SELECT * FROM experiment_configs WHERE id = ?", ("cfg_legacy",))
        row = await cur.fetchone()
        assert row is not None
        assert row["name"] == "Legacy Player"
        assert row["notes"] == "migrated note"
        assert json.loads(row["model_config"])["provider"] == "deepseek"
    finally:
        await db.close()
