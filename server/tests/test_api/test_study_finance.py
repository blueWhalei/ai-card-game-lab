"""Exact registered amounts, auditability and task admission without model calls."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app import dependencies
from app.database import connect_sqlite
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.training import CreateTrainingTaskRequest
from app.services.training_service import TrainingService
from app.utils.exceptions import AppError
from tests.test_api.test_studies import create_run, create_study


def budget(limit="10", revision=0, enabled=True, currency="CNY"):
    return {
        "expected_revision": revision,
        "currency": currency,
        "limit": limit,
        "enforcement_enabled": enabled,
        "reason": "Synthetic test budget",
    }


def expense(key="source-1", amount="0.100001", **extra):
    return {
        "request_id": key,
        "currency": "CNY",
        "amount": amount,
        "incurred_on": "2026-11-19",
        "source_type": "provider_statement",
        "source_reference": key,
        "scope_description": "Synthetic provider line allocated to this study only",
        **extra,
    }


async def setup(client):
    study = await create_study(client)
    return f"/api/v1/studies/{study['id']}"


async def test_exact_amounts_missing_zero_pagination_and_scope(client):
    path, other = await setup(client), await setup(client)
    empty = (await client.get(path + "/finance")).json()["data"]
    assert empty["recorded_amount"] is None and empty["budget"] is None
    assert (await client.put(path + "/budget", json=budget("3"))).status_code == 200
    for i in range(23):
        assert (await client.post(path + "/expenses", json=expense(f"line-{i}"))).status_code == 201
    first = (await client.get(path + "/finance")).json()["data"]
    second = (await client.get(path + "/finance?page=2")).json()["data"]
    assert first["recorded_amount"] == second["recorded_amount"] == "2.300023"
    assert first["budget_difference"] == "0.699977"
    assert first["active_count"] == first["total"] == 23
    assert len(first["items"]) == 20 and len(second["items"]) == 3
    assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}
    assert (await client.get(other + "/finance")).json()["data"]["recorded_amount"] is None
    await client.put(other + "/budget", json=budget())
    await client.post(other + "/expenses", json=expense(amount="0"))
    assert (await client.get(other + "/finance")).json()["data"]["recorded_amount"] == "0.000000"


async def test_budget_concurrency_versions_and_fixed_currency(client):
    path = await setup(client)
    results = await asyncio.gather(
        client.put(path + "/budget", json=budget("1")),
        client.put(path + "/budget", json=budget("2")),
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (
        await client.put(path + "/budget", json=budget("4", 1, currency="USD"))
    ).status_code == 409
    assert (await client.put(path + "/budget", json=budget(None, 1, False))).status_code == 200
    data = (await client.get(path + "/finance")).json()["data"]
    assert [r["revision"] for r in data["budget_history"]] == [2, 1]
    assert data["budget"]["limit"] is None and not data["admission_blocked"]


async def test_expense_idempotency_duplicates_and_retained_void(client):
    path, other = await setup(client), await setup(client)
    assert (await client.post(path + "/expenses", json=expense())).status_code == 409
    await client.put(path + "/budget", json=budget("0.1"))
    results = await asyncio.gather(
        client.post(path + "/expenses", json=expense()),
        client.post(path + "/expenses", json=expense()),
    )
    assert all(r.status_code == 201 for r in results)
    entry = results[0].json()["data"]
    assert entry["id"] == results[1].json()["data"]["id"]
    assert (await client.post(path + "/expenses", json=expense(amount="2"))).status_code == 409
    duplicate = await client.post(path + "/expenses", json=expense(request_id="new"))
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "EXPENSE_DUPLICATE"
    data = (await client.get(path + "/finance")).json()["data"]
    assert data["admission_blocked"] and data["budget_difference"] == "-0.000001"
    void_path = f"/expenses/{entry['id']}/void"
    assert (await client.post(other + void_path, json={"reason": "Wrong scope"})).status_code == 404
    for _ in range(2):
        assert (
            await client.post(path + void_path, json={"reason": "Duplicate allocation"})
        ).status_code == 200
    assert (await client.post(path + void_path, json={"reason": "Different"})).status_code == 409
    data = (await client.get(path + "/finance")).json()["data"]
    assert data["recorded_amount"] is None and not data["admission_blocked"]
    assert data["total"] == data["voided_count"] == 1
    assert data["items"][0]["source_reference"] == "source-1"
    assert data["items"][0]["void_reason"] == "Duplicate allocation"


@pytest.mark.parametrize("value", [True, 0.1, "NaN", "1e3", "-1", "1.0000001", "1000000000", "01"])
async def test_rejects_invalid_or_inexact_amounts(client, value):
    path = await setup(client)
    assert (await client.put(path + "/budget", json=budget(value))).status_code == 422
    assert (await client.post(path + "/expenses", json=expense(amount=value))).status_code == 422


async def test_required_provenance_invalid_scope_and_parameters(client):
    path = await setup(client)
    assert (await client.put(path + "/budget", json=budget(None))).status_code == 422
    assert (await client.get(path + "/finance?page=0")).status_code == 422
    assert (await client.get("/api/v1/studies/missing/finance")).status_code == 404
    for changes in [
        {"source_reference": " "},
        {"scope_description": ""},
        {"source_type": "token_estimate"},
        {"incurred_on": "invalid"},
        {"currency": "ABC"},
        {"extra": 1},
    ]:
        assert (await client.post(path + "/expenses", json=expense(**changes))).status_code == 422


async def test_budget_blocks_collection_and_start_before_execution(client):
    run = await create_run(client)
    path = f"/api/v1/studies/{run['study_id']}"
    service = dependencies.get_game_service()
    game = await service.create_game(
        "doudizhu", run["player_ids"], mode="batch", experiment_id=run["id"]
    )
    await client.put(path + "/budget", json=budget("0"))
    with patch.object(
        service._orchestration_service, "start_game_execution", new_callable=AsyncMock
    ) as start:
        response = await client.post(f"/api/v1/experiments/{run['id']}/collect", json={"count": 2})
        assert response.status_code == 409 and response.json()["code"] == "STUDY_BUDGET_REACHED"
        response = await client.post(f"/api/v1/games/{game['id']}/start")
        assert response.status_code == 409 and response.json()["code"] == "STUDY_BUDGET_REACHED"
        start.assert_not_awaited()
        assert (await service.get_game(game["id"]))["status"] == "created"
        detail = (await client.get(f"/api/v1/experiments/{run['id']}")).json()["data"]
        assert len(detail["games"]) == 1
        await client.put(path + "/budget", json=budget("0", 1, False))
        assert (await client.post(f"/api/v1/games/{game['id']}/start")).status_code == 200
        start.assert_awaited_once()


async def test_resume_budget_guard_preserves_pause_event(client, test_settings):
    run = await create_run(client)
    game = await dependencies.get_game_service().create_game(
        "doudizhu", run["player_ids"], experiment_id=run["id"]
    )
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute("UPDATE games SET status='paused' WHERE id=?", (game["id"],))
        await db.commit()
    await client.put(f"/api/v1/studies/{run['study_id']}/budget", json=budget("0"))
    orchestration = dependencies.get_game_orchestration_service()
    event = asyncio.Event()
    orchestration._pause_events[game["id"]] = event
    try:
        with pytest.raises(AppError, match="Registered expenses"):
            await orchestration.resume_game(game["id"])
        assert not event.is_set()
        assert (await dependencies.get_game_service().get_game(game["id"]))["status"] == "paused"
    finally:
        orchestration._pause_events.pop(game["id"])


async def test_training_budget_guard_prevents_task_and_background_execution(client, test_settings):
    run = await create_run(client)
    await client.put(f"/api/v1/studies/{run['study_id']}/budget", json=budget("0"))
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await DatasetRepository(db).create(
            {
                "id": "ds",
                "name": "Test",
                "game_type": "doudizhu",
                "filters": {},
                "sample_count": 0,
                "file_path": "unused",
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
    service = TrainingService.from_settings(test_settings)
    request = CreateTrainingTaskRequest(
        name="Synthetic", dataset_id="ds", base_model="synthetic", experiment_id=run["id"]
    )
    with (
        patch.object(service, "_apply_cpu_smoke_guards", new_callable=AsyncMock, return_value={}),
        patch.object(service, "_run_pipeline", new_callable=AsyncMock) as pipeline,
    ):
        with pytest.raises(AppError, match="Registered expenses"):
            await service.create_task(request)
        assert await service.list_tasks() == ([], 0)
        assert not service._cancel_flags and not service._running_tasks
        pipeline.assert_not_awaited()
