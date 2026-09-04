"""Export / import experiment and player packs."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_api.test_experiments import VALID_PLAYER_IDS, _create_experiment


async def test_export_and_import_experiment_pack(client: AsyncClient) -> None:
    created = await _create_experiment(client, name="可导出实验", collect_mode="benchmark")
    exported = await client.get(f"/api/v1/experiments/{created['id']}/export")
    assert exported.status_code == 200, exported.text
    pack = exported.json()["data"]
    assert pack["kind"] == "cardlab.experiment_pack"
    assert pack["experiment"]["name"] == "可导出实验"
    assert len(pack["players"]) == 3
    for player in pack["players"]:
        assert "api_key" not in (player.get("model_config") or {})

    imported = await client.post("/api/v1/experiments/import", json=pack)
    assert imported.status_code == 200, imported.text
    body = imported.json()["data"]
    assert body["experiment"]["id"] != created["id"]
    assert body["experiment"]["name"] == "可导出实验"
    assert body["players_reused"] == VALID_PLAYER_IDS or set(body["players_reused"]) == set(
        VALID_PLAYER_IDS
    )
    assert body["players_created"] == []
    assert body["experiment"]["protocol"]["deal_seeds"] == pack["deal_seeds"]


async def test_import_legacy_manifest_creates_experiment(client: AsyncClient) -> None:
    created = await _create_experiment(client, name="源")
    detail = await client.get(f"/api/v1/experiments/{created['id']}")
    exp = detail.json()["data"]
    legacy = {
        "experiment": {
            "id": exp["id"],
            "name": "清单导入",
            "player_ids": exp["player_ids"],
            "game_type": exp["game_type"],
            "target_games": exp["target_games"],
        },
        "protocol": exp["protocol"],
        "summary": exp["summary"],
    }
    imported = await client.post("/api/v1/experiments/import", json=legacy)
    assert imported.status_code == 200, imported.text
    assert imported.json()["data"]["experiment"]["name"] == "清单导入"


async def test_export_import_player_pack(client: AsyncClient) -> None:
    exported = await client.get("/api/v1/experiment-configs/export")
    assert exported.status_code == 200
    pack = exported.json()["data"]
    assert pack["kind"] == "cardlab.player_pack"
    assert len(pack["players"]) >= 3

    imported = await client.post("/api/v1/experiment-configs/import", json=pack)
    assert imported.status_code == 200, imported.text
    body = imported.json()["data"]
    assert len(body["players_reused"]) >= 3
    assert body["players_created"] == []


async def test_import_rejects_garbage(client: AsyncClient) -> None:
    response = await client.post("/api/v1/experiments/import", json={"hello": "world"})
    assert response.status_code == 400
