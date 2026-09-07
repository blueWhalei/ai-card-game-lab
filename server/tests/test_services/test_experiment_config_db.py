"""Experiment configs persist to SQLite; empty DB stays empty until created."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.database import init_db, open_db_connection
from app.services.experiment_config_service import ExperimentConfigService


@pytest.mark.asyncio
async def test_experiment_configs_empty_init_and_crud(tmp_path: Path) -> None:
    db_path = str(tmp_path / "app.db")
    await init_db(db_path)
    svc = ExperimentConfigService(db_path)
    await svc.initialize()
    assert svc.list_configs() == []

    created = await svc.create_config(
        {
            "id": "cfg_temp_09",
            "name": "Temp 0.9",
            "notes": "created in test",
            "model_config": {
                "provider": "ollama",
                "model_name": "llama",
                "temperature": 0.9,
                "top_p": 0.95,
                "max_tokens": 128,
            },
        }
    )
    assert created["id"] == "cfg_temp_09"
    assert created["notes"] == "created in test"
    assert "avatar" not in created

    extra = await svc.create_config(
        {
            "id": "cfg_b",
            "name": "B",
            "notes": "",
            "model_config": {"provider": "openai", "model_name": "gpt"},
        }
    )
    assert extra["id"] == "cfg_b"

    svc2 = ExperimentConfigService(db_path)
    await svc2.initialize()
    assert len(svc2.list_configs()) == 2
    await svc2.delete_config("cfg_temp_09")
    assert svc2.get_config("cfg_temp_09") is None


@pytest.mark.asyncio
async def test_migrate_retired_deepseek_models(tmp_path: Path) -> None:
    db_path = str(tmp_path / "app.db")
    await init_db(db_path)
    svc = ExperimentConfigService(db_path)
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
