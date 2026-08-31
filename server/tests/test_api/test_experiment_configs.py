"""Tests for experiment config API endpoints."""

from __future__ import annotations

from httpx import AsyncClient

from app.config import Settings
from app.database import open_db_connection
from app.dependencies import get_experiment_config_service
from app.repositories.experiment_config_repo import ExperimentConfigRepository


async def test_list_and_stats(client: AsyncClient) -> None:
    response = await client.get("/api/v1/experiment-configs")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)

    stats_response = await client.get("/api/v1/experiment-configs/stats")
    assert stats_response.status_code == 200
    stats_body = stats_response.json()
    assert stats_body["code"] == 0
    assert isinstance(stats_body["data"], list)


async def test_create_get_update_delete(client: AsyncClient) -> None:
    create_payload = {
        "id": "test_cfg_api",
        "name": "API Test Config",
        "notes": "created via API test",
        "model_config_data": {
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 512,
        },
    }
    create_response = await client.post("/api/v1/experiment-configs", json=create_payload)
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["id"] == "test_cfg_api"
    assert created["notes"] == "created via API test"
    assert "avatar" not in created

    get_response = await client.get("/api/v1/experiment-configs/test_cfg_api")
    assert get_response.status_code == 200
    assert get_response.json()["data"]["name"] == "API Test Config"

    update_response = await client.put(
        "/api/v1/experiment-configs/test_cfg_api",
        json={"notes": "updated note"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["notes"] == "updated note"

    delete_response = await client.delete("/api/v1/experiment-configs/test_cfg_api")
    assert delete_response.status_code == 204

    missing_response = await client.get("/api/v1/experiment-configs/test_cfg_api")
    assert missing_response.status_code == 404
    assert missing_response.json()["code"] == "EXPERIMENT_CONFIG_NOT_FOUND"


async def test_create_conflict(client: AsyncClient) -> None:
    payload = {
        "id": "dup_cfg",
        "name": "Dup",
        "notes": "",
        "model_config_data": {
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "temperature": 0.5,
            "top_p": 0.9,
            "max_tokens": 256,
        },
    }
    first = await client.post("/api/v1/experiment-configs", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/experiment-configs", json=payload)
    assert second.status_code == 409
    assert second.json()["code"] == "EXPERIMENT_CONFIG_CONFLICT"


async def test_create_rejects_blank_id(client: AsyncClient) -> None:
    payload = {
        "id": "   ",
        "name": "Blank",
        "notes": "",
        "model_config_data": {
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "temperature": 0.5,
            "top_p": 0.9,
            "max_tokens": 256,
        },
    }
    response = await client.post("/api/v1/experiment-configs", json=payload)
    assert response.status_code == 422


async def test_delete_by_query_and_blank_id(client: AsyncClient, test_settings: Settings) -> None:
    payload = {
        "id": "query_del_cfg",
        "name": "Query Delete",
        "notes": "",
        "model_config_data": {
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "temperature": 0.5,
            "top_p": 0.9,
            "max_tokens": 256,
        },
    }
    created = await client.post("/api/v1/experiment-configs", json=payload)
    assert created.status_code == 201

    missing_query = await client.delete("/api/v1/experiment-configs")
    assert missing_query.status_code == 422

    deleted = await client.delete("/api/v1/experiment-configs", params={"id": "query_del_cfg"})
    assert deleted.status_code == 204

    service = get_experiment_config_service()
    db = await open_db_connection(test_settings.sqlite_path)
    try:
        await ExperimentConfigRepository(db).upsert(
            {
                "id": "",
                "name": "legacy blank",
                "notes": "pre-validation row",
                "model_config": payload["model_config_data"],
            }
        )
    finally:
        await db.close()
    await service.initialize()

    blank_deleted = await client.delete("/api/v1/experiment-configs", params={"id": ""})
    assert blank_deleted.status_code == 204

    listed = await client.get("/api/v1/experiment-configs")
    ids = [row["id"] for row in listed.json()["data"]]
    assert "" not in ids
    assert "query_del_cfg" not in ids
