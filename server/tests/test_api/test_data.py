"""Tests for the data API endpoints."""

from httpx import AsyncClient

from app.database import open_db_connection
from app.dependencies import get_settings


async def test_data_stats(client: AsyncClient) -> None:
    response = await client.get("/api/v1/data/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert "total_games" in data
    assert "total_rounds" in data


async def test_data_stats_filters_by_experiment(client: AsyncClient) -> None:
    settings = get_settings()
    conn = await open_db_connection(settings.sqlite_path)
    try:
        await conn.execute(
            """
            INSERT INTO experiments (id, name, notes, game_type, player_ids,
                                    target_games, created_at, updated_at)
            VALUES ('exp_stats', 'scoped', '', 'doudizhu', '["a","b","c"]',
                    1, '2026-08-30T00:00:00+00:00', '2026-08-30T00:00:00+00:00')
            """
        )
        await conn.execute(
            """
            INSERT INTO games (id, game_type, status, player_ids, data_file,
                               created_at, experiment_id)
            VALUES ('g_exp', 'doudizhu', 'finished', '[]', 'a.jsonl',
                    '2026-08-30T00:00:00+00:00', 'exp_stats')
            """
        )
        await conn.execute(
            """
            INSERT INTO games (id, game_type, status, player_ids, data_file, created_at)
            VALUES ('g_scatter', 'doudizhu', 'finished', '[]', 'b.jsonl',
                    '2026-08-30T00:00:00+00:00')
            """
        )
        await conn.commit()
    finally:
        await conn.close()

    scoped = await client.get("/api/v1/data/stats", params={"experiment_id": "exp_stats"})
    assert scoped.status_code == 200
    assert scoped.json()["data"]["total_games"] == 1

    global_stats = await client.get("/api/v1/data/stats")
    assert global_stats.status_code == 200
    assert global_stats.json()["data"]["total_games"] >= 2


async def test_list_datasets_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/datasets")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == []
