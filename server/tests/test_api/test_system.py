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
    assert engines["doudizhu"]["phases"] == ["bidding", "playing"]
    assert engines["doudizhu"]["prompt_keys"]["playing"] == "doudizhu_playing"
    assert engines["doudizhu"]["benchmark_seed_count"] > 0
    assert "benchmark_seeds" not in engines["doudizhu"]
    assert "role:landlord" in engines["doudizhu"]["eval_metric_ids"]


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


async def test_preflight_all_scope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/preflight", params={"scope": "all"})
    assert response.status_code == 200
    data = response.json()["data"]
    ids = {c["id"] for c in data["checks"]}
    assert "providers_any" in ids
    assert "training_deps" in ids
    assert "memory_smoke" in ids
    assert isinstance(data["can_collect"], bool)
    assert isinstance(data["can_train"], bool)
    assert "data_dirs_ready" not in data
    assert "seed_provider" not in data


async def test_preflight_collect_with_experiment(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/experiments",
        json={
            "name": "preflight-exp",
            "player_ids": ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"],
            "target_games": 2,
        },
    )
    assert create.status_code == 201, create.text
    exp_id = create.json()["data"]["id"]
    response = await client.get(
        "/api/v1/system/preflight",
        params={"scope": "collect", "experiment_id": exp_id},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    ids = {c["id"] for c in data["checks"]}
    assert "protocol" in ids
    assert "providers_seats" in ids
    assert "providers_any" not in ids
    for item in data["checks"]:
        assert item["id"]
        assert item["message"]
    seats = next(c for c in data["checks"] if c["id"] == "providers_seats")
    if not seats["ok"]:
        params = seats.get("params") or {}
        assert params.get("providers") or params.get("incomplete") is True
