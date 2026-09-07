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
    dataset = protocol.get("dataset") or {}
    engine = protocol.get("engine") or {}
    expected_seeds = dataset.get("deal_seeds") or []
    assert len(expected_seeds) == 3
    assert protocol.get("schema_version") == 2
    assert engine.get("engine_version") == "1"
    assert engine.get("game_type") == "doudizhu"

    with (
        patch(
            "app.services.game_service.is_provider_configured",
            return_value=True,
        ),
        patch(
            "app.services.game_service.GameService.start_game",
            new_callable=AsyncMock,
            side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
        ),
    ):
        first = await client.post(
            f"/api/v1/experiments/{exp['id']}/collect",
            json={"count": 2},
        )
        second = await client.post(
            f"/api/v1/experiments/{exp['id']}/collect",
            json={"count": 1},
        )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    detail = await client.get(f"/api/v1/experiments/{exp['id']}")
    body = detail.json()["data"]
    games = body["games"]
    assert len(games) == 3
    games_sorted = sorted(games, key=lambda g: g["created_at"])
    seeds = [(g.get("metadata") or {}).get("deal_seed") for g in games_sorted]
    assert seeds == expected_seeds

    coverage = body["benchmark"]
    assert coverage["seed_total"] == 3
    assert coverage["seed_started"] == 3
    assert coverage["seed_running"] == 3
    assert coverage["seed_remaining"] == 0
    assert coverage["extra_games"] == 0
    assert coverage["complete"] is False

    frozen = list(expected_seeds)
    with (
        patch(
            "app.services.game_service.is_provider_configured",
            return_value=True,
        ),
        patch(
            "app.services.game_service.GameService.start_game",
            new_callable=AsyncMock,
            side_effect=lambda game_id, db=None: {"id": game_id, "status": "running"},
        ),
    ):
        overflow = await client.post(
            f"/api/v1/experiments/{exp['id']}/collect",
            json={"count": 1},
        )
    assert overflow.status_code == 400, overflow.text
    after = await client.get(f"/api/v1/experiments/{exp['id']}")
    after_body = after.json()["data"]
    after_sorted = sorted(after_body["games"], key=lambda g: g["created_at"])
    assert [(g.get("metadata") or {}).get("deal_seed") for g in after_sorted] == seeds
    assert (after_body.get("protocol") or {}).get("dataset", {}).get("deal_seeds") == frozen


async def test_free_experiment_has_null_benchmark(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/experiments",
        json={
            "name": "free-run",
            "player_ids": VALID_PLAYER_IDS,
            "target_games": 3,
            "collect_mode": "free",
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["data"]["benchmark"] is None

    detail = await client.get(f"/api/v1/experiments/{create.json()['data']['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["benchmark"] is None
