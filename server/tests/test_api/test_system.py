"""Tests for the system API endpoints."""

from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_game_types(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/game-types")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)


async def test_engines_include_doudizhu_player_slots(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/engines")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    engines = {item["id"]: item for item in body["data"]}
    assert engines["doudizhu"]["min_players"] == 3
    assert engines["doudizhu"]["max_players"] == 3


async def test_seed_demo_is_idempotent(client: AsyncClient) -> None:
    first = await client.post("/api/v1/system/seed-demo")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["code"] == 0
    assert first_body["data"]["created"] is True
    assert first_body["data"]["game_id"] == "game_demo_doudizhu"

    second = await client.post("/api/v1/system/seed-demo")
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["data"]["created"] is False
    assert second_body["data"]["game_id"] == "game_demo_doudizhu"


async def test_startup_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/startup-check")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["data_dirs_ready"] is True
    assert "can_collect" in data
    assert "warnings" in data
    assert isinstance(data["providers"], list)
