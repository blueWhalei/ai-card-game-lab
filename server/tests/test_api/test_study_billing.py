"""Snapshot replacement, provenance, failure states and independent task admission."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from app import dependencies
from app.database import connect_sqlite
from app.services.openai_costs import billing_error
from app.services.study_finance_service import ensure_study_budget
from app.utils.exceptions import AppError
from tests.test_api.test_studies import create_run, create_study
from tests.test_api.test_study_finance import budget, expense


@pytest.fixture
def credentials(client, monkeypatch):
    settings = dependencies.get_settings()
    monkeypatch.setattr(settings, "openai_billing_admin_key", SecretStr("admin-test"))
    monkeypatch.setattr(settings, "openai_billing_organization_id", "org-test")
    return settings


def config(revision=0, enabled=True, **changes):
    return {
        "expected_revision": revision,
        "project_id": "proj_test",
        "start_date": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
        "limit": "0.2",
        "enforcement_enabled": enabled,
        "max_age_hours": 6,
        "reason": "Synthetic scope; not actual research costs",
        **changes,
    }


def lines(amount="0.1", count=1):
    return [
        {
            "start_time": 100,
            "end_time": 200,
            "amount": amount,
            "currency": "USD",
            "project_id": "proj_test",
            "line_item": f"item-{i}",
        }
        for i in range(count)
    ]


async def setup(client):
    run = await create_run(client)
    return run, f"/api/v1/studies/{run['study_id']}"


async def sync(client, path, revision=1):
    return await client.post(path + "/billing/sync", json={"expected_revision": revision})


async def guard(settings, run):
    async with connect_sqlite(settings.sqlite_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await ensure_study_budget(db, run["id"])
        finally:
            await db.rollback()


async def test_snapshot_replacement_scope_pagination_and_independent_manual_totals(
    client, credentials
):
    run, path = await setup(client)
    await client.put(path + "/budget", json=budget("10"))
    await client.post(path + "/expenses", json=expense(amount="0.1"))
    assert (await client.put(path + "/billing/config", json=config(limit="1"))).status_code == 200
    missing = (await client.get(path + "/billing")).json()["data"]
    assert missing["admission_blocked"] and missing["snapshot"] is None
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines("0.0000001", 23),
    ):
        for _ in range(2):
            assert (await sync(client, path)).status_code == 200
    data = (await client.get(path + "/billing")).json()["data"]
    assert data["snapshot"]["amount"] == "0.0000023" and len(data["history"]) == 2
    assert not data["admission_blocked"] and "admin-test" not in str(data)
    endpoint = path + "/billing/attempts/" + data["snapshot"]["id"]
    first = (await client.get(endpoint)).json()["data"]
    second = (await client.get(endpoint + "?page=2")).json()["data"]
    assert first["total"] == second["total"] == 23
    assert len(first["items"]) == 20 and len(second["items"]) == 3
    assert first["organization_id"] == "org-test" and first["project_id"] == "proj_test"
    other = await create_study(client)
    assert (
        await client.get(f"/api/v1/studies/{other['id']}/billing/attempts/{data['snapshot']['id']}")
    ).status_code == 404
    assert (await client.get(path + "/finance")).json()["data"]["recorded_amount"] == "0.100000"
    await guard(credentials, run)


async def test_failure_preserves_history_but_blocks_and_recovery_reopens(client, credentials):
    run, path = await setup(client)
    await client.put(path + "/billing/config", json=config())
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines(),
    ):
        await sync(client, path)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        side_effect=billing_error("BILLING_NETWORK"),
    ):
        assert (await sync(client, path)).status_code == 502
    data = (await client.get(path + "/billing")).json()["data"]
    assert data["state"] == "failed" and data["snapshot"]["amount"] == "0.1"
    assert data["latest_attempt"]["amount"] is None
    with pytest.raises(AppError) as error:
        await guard(credentials, run)
    assert error.value.code == "SUPPLIER_BILLING_UNAVAILABLE"
    started, release = asyncio.Event(), asyncio.Event()

    async def delayed(*args):
        started.set()
        await release.wait()
        return lines()

    with patch("app.services.study_billing_service.OpenAICostsClient.fetch", side_effect=delayed):
        task = asyncio.create_task(sync(client, path))
        await started.wait()
        try:
            with pytest.raises(AppError):
                await guard(credentials, run)
        finally:
            release.set()
        assert (await task).status_code == 200
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines(),
    ):
        await sync(client, path)
    await guard(credentials, run)
    with patch(
        "app.services.study_billing_service.utc_now",
        return_value=datetime.now(UTC) + timedelta(hours=6),
    ):
        assert (await client.get(path + "/billing")).json()["data"]["state"] == "stale"
        with pytest.raises(AppError):
            await guard(credentials, run)


async def test_concurrent_sync_and_config_change_cannot_adopt_old_snapshot(client, credentials):
    _, path = await setup(client)
    await client.put(path + "/billing/config", json=config())
    started, release = asyncio.Event(), asyncio.Event()

    async def delayed(*args):
        started.set()
        await release.wait()
        return lines()

    with patch("app.services.study_billing_service.OpenAICostsClient.fetch", side_effect=delayed):
        task = asyncio.create_task(sync(client, path))
        await started.wait()
        second = await sync(client, path)
        assert second.status_code == 409 and second.json()["code"] == "BILLING_BUSY"
        assert (
            await client.put(path + "/billing/config", json=config(1, project_id="proj_new"))
        ).status_code == 200
        release.set()
        assert (await task).status_code == 409
    data = (await client.get(path + "/billing")).json()["data"]
    assert (
        data["config"]["revision"] == 2 and data["snapshot"] is None and data["admission_blocked"]
    )
    assert data["history"][0]["project_id"] == "proj_test"
    assert [row["revision"] for row in data["config_history"]] == [2, 1]
    assert (await sync(client, path)).json()["code"] == "BILLING_CONFLICT"


async def test_limit_zero_blocks_collection_and_start_before_execution(client, credentials):
    run, path = await setup(client)
    await client.put(path + "/billing/config", json=config(limit="0"))
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=[],
    ):
        data = (await sync(client, path)).json()["data"]
    assert data["snapshot"]["amount"] == "0" and data["state"] == "reached"
    service = dependencies.get_game_service()
    game = await service.create_game(
        "doudizhu", run["player_ids"], mode="batch", experiment_id=run["id"]
    )
    with patch.object(
        service._orchestration_service, "start_game_execution", new_callable=AsyncMock
    ) as start:
        response = await client.post(f"/api/v1/experiments/{run['id']}/collect", json={"count": 2})
        assert response.status_code == 409 and response.json()["code"] == "SUPPLIER_BUDGET_REACHED"
        assert (await client.post(f"/api/v1/games/{game['id']}/start")).status_code == 409
        start.assert_not_awaited()
        assert (await service.get_game(game["id"]))["status"] == "created"
    await client.put(path + "/billing/config", json=config(1, False, limit="0"))
    await guard(credentials, run)


async def test_config_versions_validation_and_credential_isolation(
    client, credentials, monkeypatch
):
    _, path = await setup(client)
    results = await asyncio.gather(
        *[client.put(path + "/billing/config", json=config()) for _ in range(2)]
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    for extra in [
        {"project_id": "all"},
        {"max_age_hours": True},
        {"max_age_hours": 25},
        {"limit": None},
        {"limit": 1},
        {"start_date": "2099-01-01"},
    ]:
        assert (
            await client.put(path + "/billing/config", json=config(1, **extra))
        ).status_code == 422
    monkeypatch.setattr(credentials, "openai_billing_organization_id", "org-other")
    assert (await sync(client, path)).json()["code"] == "BILLING_NOT_CONFIGURED"
    monkeypatch.setattr(credentials, "openai_billing_organization_id", "")
    monkeypatch.setattr(credentials, "openai_billing_admin_key", SecretStr(""))
    assert (await client.put(path + "/billing/config", json=config(1, False))).status_code == 200
    data = (await client.get(path + "/billing")).json()["data"]
    assert not data["can_sync"] and not data["admission_blocked"]


async def test_expired_running_lease_is_blocked_and_retry_retains_attempt(client, credentials):
    run, path = await setup(client)
    await client.put(path + "/billing/config", json=config())
    old = datetime.now(UTC) - timedelta(minutes=4)
    async with connect_sqlite(credentials.sqlite_path) as db:
        await db.execute(
            "INSERT INTO study_billing_attempts (id,study_id,revision,status,start_time,end_time,started_at) VALUES ('abandoned',?,1,'running',100,200,?)",
            (run["study_id"], old.isoformat()),
        )
        await db.commit()
    assert (await client.get(path + "/billing")).json()["data"]["state"] == "interrupted"
    with pytest.raises(AppError):
        await guard(credentials, run)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines(),
    ):
        assert (await sync(client, path)).status_code == 200
    history = (await client.get(path + "/billing")).json()["data"]["history"]
    assert history[1]["status"] == "interrupted" and history[1]["amount"] is None
