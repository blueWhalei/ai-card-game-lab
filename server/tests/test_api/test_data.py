"""Tests for the data API endpoints."""

from httpx import AsyncClient


async def test_data_stats(client: AsyncClient) -> None:
    response = await client.get("/api/v1/data/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert "total_games" in data
    assert "total_rounds" in data


async def test_list_datasets_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/data/datasets")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0
