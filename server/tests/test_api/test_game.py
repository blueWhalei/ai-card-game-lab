"""Tests for the game API endpoints."""

from httpx import AsyncClient


async def test_list_games(client: AsyncClient) -> None:
    response = await client.get("/api/v1/games")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert "items" in body["data"]
    assert "total" in body["data"]


async def test_create_game(client: AsyncClient) -> None:
    payload = {
        "game_type": "doudizhu",
        "player_ids": ["player_a", "player_b", "player_c"],
    }
    response = await client.post("/api/v1/games", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["game_type"] == "doudizhu"
    assert body["data"]["status"] == "created"
    assert len(body["data"]["player_ids"]) == 3


async def test_get_game(client: AsyncClient) -> None:
    # Create first
    res = await client.post("/api/v1/games", json={
        "game_type": "doudizhu",
        "player_ids": ["p1", "p2", "p3"],
    })
    game_id = res.json()["data"]["id"]
    # Get
    response = await client.get(f"/api/v1/games/{game_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == game_id


async def test_game_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/games/nonexistent_id")
    assert response.status_code == 404
