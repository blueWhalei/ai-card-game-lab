"""AI players persist to SQLite and seed from YAML when empty."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.database import init_db
from app.services.ai_player_service import AIPlayerService


@pytest.mark.asyncio
async def test_ai_players_seed_and_crud(tmp_path: Path) -> None:
    db_path = str(tmp_path / "app.db")
    yaml_path = tmp_path / "ai_players.yaml"
    yaml_path.write_text(
        yaml.dump(
            {
                "players": [
                    {
                        "id": "p1",
                        "name": "One",
                        "description": "seed",
                        "avatar": "A",
                        "model_config": {
                            "provider": "ollama",
                            "model_name": "llama",
                            "temperature": 0.5,
                            "top_p": 0.9,
                            "max_tokens": 128,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    await init_db(db_path)
    svc = AIPlayerService(db_path, str(yaml_path))
    await svc.initialize()

    players = svc.list_players()
    assert len(players) == 1
    assert players[0]["id"] == "p1"

    created = await svc.create_player(
        {
            "id": "p2",
            "name": "Two",
            "model_config": {"provider": "openai", "model_name": "gpt"},
        }
    )
    assert created["id"] == "p2"
    assert svc.get_player("p2") is not None

    # Re-init from DB (no re-seed)
    svc2 = AIPlayerService(db_path, str(yaml_path))
    await svc2.initialize()
    assert len(svc2.list_players()) == 2

    await svc2.delete_player("p1")
    assert svc2.get_player("p1") is None


@pytest.mark.asyncio
async def test_migrate_retired_deepseek_models(tmp_path: Path) -> None:
    db_path = str(tmp_path / "app.db")
    await init_db(db_path)
    svc = AIPlayerService(db_path, yaml_seed_path=None)
    # Bypass seed: create players then re-init with migration
    from app.database import open_db_connection
    from app.repositories.ai_player_repo import AIPlayerRepository

    db = await open_db_connection(db_path)
    try:
        repo = AIPlayerRepository(db)
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
    player = svc.get_player("legacy")
    assert player is not None
    assert player["model_config"]["model_name"] == "deepseek-v4-flash"
