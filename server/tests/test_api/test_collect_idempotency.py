"""Batch reservations survive concurrency, retries and startup failures."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app import dependencies
from app.database import connect_sqlite
from app.services.game_service import GameService


async def create_experiment(client: AsyncClient, benchmark: bool = False) -> str:
    response = await client.post(
        "/api/v1/experiments",
        json={
            "name": "idempotency",
            "player_ids": ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"],
            "target_games": 4,
            "collect_mode": "benchmark" if benchmark else "free",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["data"]["id"])


async def detail(client: AsyncClient, experiment_id: str) -> dict[str, Any]:
    response = await client.get(f"/api/v1/experiments/{experiment_id}")
    return response.json()["data"]


async def test_same_key_concurrently_starts_once(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    exp = await create_experiment(client)
    start = AsyncMock()
    monkeypatch.setattr(
        dependencies.get_game_orchestration_service(), "start_game_execution", start
    )
    responses = await asyncio.gather(
        *(
            client.post(
                f"/api/v1/experiments/{exp}/collect", json={"count": 2, "idempotency_key": "same"}
            )
            for _ in range(2)
        )
    )
    assert all(response.status_code == 201 for response in responses)
    assert responses[0].json() == responses[1].json()
    assert start.await_count == 2
    assert len((await detail(client, exp))["games"]) == 2
    conflict = await client.post(
        f"/api/v1/experiments/{exp}/collect", json={"count": 1, "idempotency_key": "same"}
    )
    assert conflict.status_code == 409
    assert start.await_count == 2


async def test_distinct_concurrent_batches_reserve_disjoint_seeds(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    exp = await create_experiment(client, benchmark=True)
    monkeypatch.setattr(
        dependencies.get_game_orchestration_service(), "start_game_execution", AsyncMock()
    )
    responses = await asyncio.gather(
        *(
            client.post(
                f"/api/v1/experiments/{exp}/collect", json={"count": 2, "idempotency_key": key}
            )
            for key in ("first", "second")
        )
    )
    assert all(response.status_code == 201 for response in responses)
    state = await detail(client, exp)
    seeds = [game["metadata"]["deal_seed"] for game in state["games"]]
    assert len(seeds) == len(set(seeds)) == 4
    assert set(seeds) == set(state["protocol"]["dataset"]["deal_seeds"])


async def test_preparation_failure_rolls_back_whole_batch(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    exp = await create_experiment(client)
    original = GameService.create_game
    attempts = 0

    async def create(self: GameService, *args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("second reservation failed")
        return await original(self, *args, **kwargs)

    start = AsyncMock()
    monkeypatch.setattr(GameService, "create_game", create)
    monkeypatch.setattr(
        dependencies.get_game_orchestration_service(), "start_game_execution", start
    )
    with pytest.raises(RuntimeError, match="reservation failed"):
        await client.post(
            f"/api/v1/experiments/{exp}/collect", json={"count": 2, "idempotency_key": "retry"}
        )
    state = await detail(client, exp)
    assert state["games"] == []
    assert state["protocol"]["dataset"]["deal_seeds"] == []
    start.assert_not_awaited()
    async with connect_sqlite(dependencies.get_settings().sqlite_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM experiment_collect_requests")
        assert (await cursor.fetchone())[0] == 0
    monkeypatch.setattr(GameService, "create_game", original)
    retry = await client.post(
        f"/api/v1/experiments/{exp}/collect", json={"count": 2, "idempotency_key": "retry"}
    )
    assert retry.status_code == 201
    assert start.await_count == 2


async def test_start_failure_retry_reuses_reserved_games(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    exp = await create_experiment(client)
    start = AsyncMock(side_effect=[None, RuntimeError("start failed"), None])
    monkeypatch.setattr(
        dependencies.get_game_orchestration_service(), "start_game_execution", start
    )
    payload = {"count": 2, "idempotency_key": "resume"}
    with pytest.raises(RuntimeError, match="start failed"):
        await client.post(f"/api/v1/experiments/{exp}/collect", json=payload)
    before = await detail(client, exp)
    assert sorted(game["status"] for game in before["games"]) == ["created", "running"]
    # A new service instance still finds the persisted reservation.
    dependencies.get_experiment_service.cache_clear()
    retry = await client.post(f"/api/v1/experiments/{exp}/collect", json=payload)
    assert retry.status_code == 201, retry.text
    after = await detail(client, exp)
    assert {game["id"] for game in before["games"]} == set(retry.json()["data"]["game_ids"])
    assert before["protocol"]["dataset"] == after["protocol"]["dataset"]
    assert all(game["status"] == "running" for game in after["games"])
    assert start.await_count == 3
    again = await client.post(f"/api/v1/experiments/{exp}/collect", json=payload)
    assert again.json() == retry.json()
    assert start.await_count == 3


async def test_archived_games_do_not_rewind_reservation_index(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    exp = await create_experiment(client, benchmark=True)
    monkeypatch.setattr(
        dependencies.get_game_orchestration_service(), "start_game_execution", AsyncMock()
    )
    url = f"/api/v1/experiments/{exp}/collect"
    first = await client.post(url, json={"count": 2, "idempotency_key": "old"})
    assert first.status_code == 201
    async with connect_sqlite(dependencies.get_settings().sqlite_path) as db:
        await db.execute("DELETE FROM games WHERE experiment_id = ?", (exp,))
        await db.commit()
    replay = await client.post(url, json={"count": 2, "idempotency_key": "old"})
    assert replay.json() == first.json()
    second = await client.post(url, json={"count": 2, "idempotency_key": "new"})
    assert second.status_code == 201
    state = await detail(client, exp)
    seeds = [game["metadata"]["deal_seed"] for game in state["games"]]
    assert set(seeds) == set(state["protocol"]["dataset"]["deal_seeds"][2:])
