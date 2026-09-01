"""Benchmark-mode experiment collect uses fixed deal seeds."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

VALID_PLAYER_IDS = ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"]


async def test_benchmark_collect_uses_fixed_seeds(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/experiments",
        json={
            "name": "benchmark-run",
            "player_ids": VALID_PLAYER_IDS,
            "target_games": 3,
            "collect_mode": "benchmark",
        },
    )
    assert create.status_code == 201, create.text
    exp = create.json()["data"]
    protocol = exp.get("protocol") or {}
    expected_seeds = protocol.get("deal_seeds") or []
    assert len(expected_seeds) == 3

    with patch(
        "app.services.game_service.GameService.start_game",
        new_callable=AsyncMock,
        side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
    ):
        first = await client.post(
            f"/api/v1/experiments/{exp['id']}/collect",
            json={"count": 2},
        )
        second = await client.post(
            f"/api/v1/experiments/{exp['id']}/collect",
            json={"count": 1},
        )

    assert first.status_code == 201
    assert second.status_code == 201

    detail = await client.get(f"/api/v1/experiments/{exp['id']}")
    games = detail.json()["data"]["games"]
    assert len(games) == 3
    games_sorted = sorted(games, key=lambda g: g["created_at"])
    seeds = [(g.get("metadata") or {}).get("deal_seed") for g in games_sorted]
    assert seeds == expected_seeds
