"""Tests for experiment config API endpoints."""

from __future__ import annotations

from httpx import AsyncClient


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
