"""Persistent scheduling, concurrent claims, recovery and unchanged cost admission scope."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.database import connect_sqlite
from app.main import create_app
from app.services.billing_scheduler import BillingScheduler
from app.services.openai_costs import billing_error
from app.services.study_billing_service import StudyBillingService
from app.utils.exceptions import AppError
from tests.test_api.test_study_billing import config, guard, lines, setup, sync
from tests.test_api.test_study_billing import credentials as credentials


def plan(revision=0, config_revision=1, enabled=True, interval=60):
    return {
        "expected_revision": revision,
        "expected_config_revision": config_revision,
        "enabled": enabled,
        "interval_minutes": interval,
        "reason": "Synthetic schedule review",
    }


async def prepare(client):
    run, path = await setup(client)
    assert (await client.put(path + "/billing/config", json=config())).status_code == 200
    assert (await client.put(path + "/billing/schedule", json=plan())).status_code == 200
    return run, path


async def drain(worker):
    await asyncio.gather(*list(worker.jobs.values()))
    await asyncio.sleep(0)


async def due(settings, study_id):
    async with connect_sqlite(settings.sqlite_path) as db:
        await db.execute(
            "UPDATE study_billing_schedule_runtime SET next_due_at=? WHERE study_id=?",
            ((datetime.now(UTC) - timedelta(days=1)).isoformat(), study_id),
        )
        await db.commit()


async def test_default_off_strict_validation_and_schedule_versions(client, credentials):
    run, path = await setup(client)
    response = (await client.get(path + "/billing/schedule")).json()["data"]
    assert response["plan"] is None and response["state"] == "not_configured"
    assert not response["worker_recent"]
    assert (await client.put(path + "/billing/schedule", json=plan())).status_code == 409
    await client.put(path + "/billing/config", json=config(max_age_hours=1))
    assert (await client.put(path + "/billing/schedule", json=plan(interval=31))).json()[
        "code"
    ] == "BILLING_SCHEDULE_INTERVAL"
    for values in [
        {"interval_minutes": 14},
        {"interval_minutes": True},
        {"enabled": 1},
        {"reason": " "},
    ]:
        assert (
            await client.put(path + "/billing/schedule", json={**plan(), **values})
        ).status_code == 422
    results = await asyncio.gather(
        *[client.put(path + "/billing/schedule", json=plan(interval=30)) for _ in range(2)]
    )
    assert sorted(response.status_code for response in results) == [200, 409]
    await client.put(path + "/billing/schedule", json=plan(1, enabled=False, interval=720))
    result = (await client.get(path + "/billing/schedule")).json()["data"]
    assert result["state"] == "paused" and result["plan"]["next_due_at"] is None
    assert [version["revision"] for version in result["history"]] == [2, 1]
    with pytest.raises(AppError):
        await guard(credentials, run)
    assert (await client.get("/api/v1/studies/missing/billing/schedule")).status_code == 404


async def test_due_plan_resumes_after_restart_without_catchup_burst(client, credentials):
    run, path = await prepare(client)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines(),
    ) as fetch:
        first = BillingScheduler(credentials)
        await first.tick()
        await drain(first)
        assert fetch.await_count == 1
        state = (await client.get(path + "/billing/schedule")).json()["data"]
        assert state["state"] == "scheduled" and state["worker_recent"]
        current = state["plan"]
        assert datetime.fromisoformat(current["next_due_at"]) - datetime.fromisoformat(
            current["updated_at"]
        ) == timedelta(minutes=60)
        second = BillingScheduler(credentials)
        await second.tick()
        await drain(second)
        assert fetch.await_count == 1
        await due(credentials, run["study_id"])
        await second.tick()
        await drain(second)
        await second.tick()
        await drain(second)
        assert fetch.await_count == 2
    result = (await client.get(path + "/billing")).json()["data"]
    assert result["snapshot"]["amount"] == "0.1" and len(result["history"]) == 2
    assert all(
        item["trigger"] == "scheduled" and item["schedule_revision"] == 1
        for item in result["history"]
    )
    await guard(credentials, run)


async def test_manual_and_two_workers_share_one_inflight_claim(client, credentials):
    _, path = await prepare(client)
    started, release = asyncio.Event(), asyncio.Event()

    async def pending(*args):
        started.set()
        await release.wait()
        return lines()

    first, second = BillingScheduler(credentials), BillingScheduler(credentials)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch", side_effect=pending
    ) as fetch:
        await asyncio.gather(first.tick(), second.tick())
        await started.wait()
        try:
            response = await sync(client, path)
            assert response.status_code == 409 and response.json()["code"] == "BILLING_BUSY"
            assert fetch.await_count == 1
        finally:
            release.set()
        await asyncio.gather(drain(first), drain(second))
    assert len((await client.get(path + "/billing")).json()["data"]["history"]) == 1


@pytest.mark.parametrize(
    "code",
    [
        "BILLING_NETWORK",
        "BILLING_RATE_LIMIT",
        "BILLING_REMOTE",
        "BILLING_AUTH",
        "BILLING_RESPONSE",
        "BILLING_PERIOD",
    ],
)
async def test_failure_policy_manual_recovery_and_budget_remains_independent(
    client, credentials, code
):
    run, path = await prepare(client)
    worker = BillingScheduler(credentials)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        side_effect=billing_error(code),
    ):
        await worker.tick()
        await drain(worker)
    result = (await client.get(path + "/billing/schedule")).json()["data"]
    retryable = code in ("BILLING_NETWORK", "BILLING_RATE_LIMIT", "BILLING_REMOTE")
    assert result["state"] == ("retry_wait" if retryable else "attention")
    assert result["plan"]["consecutive_failures"] == 1 and result["plan"]["error_code"] == code
    if retryable:
        assert datetime.fromisoformat(result["plan"]["next_due_at"]) - datetime.fromisoformat(
            result["plan"]["updated_at"]
        ) == timedelta(minutes=120)
    else:
        assert result["plan"]["next_due_at"] is None
    with pytest.raises(AppError):
        await guard(credentials, run)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines("0.3"),
    ):
        await sync(client, path)
    result = (await client.get(path + "/billing/schedule")).json()["data"]
    assert result["state"] == "scheduled" and result["plan"]["consecutive_failures"] == 0
    with pytest.raises(AppError) as error:
        await guard(credentials, run)
    assert error.value.code == "SUPPLIER_BUDGET_REACHED"
    await client.put(path + "/billing/schedule", json=plan(1, enabled=False))
    with pytest.raises(AppError):
        await guard(credentials, run)


async def test_backoff_is_bounded_and_missing_credentials_are_audited(
    client, credentials, monkeypatch
):
    run, path = await prepare(client)
    async with connect_sqlite(credentials.sqlite_path) as db:
        await db.execute(
            "UPDATE study_billing_schedule_runtime SET consecutive_failures=20 WHERE study_id=?",
            (run["study_id"],),
        )
        await db.commit()
    worker = BillingScheduler(credentials)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        side_effect=billing_error("BILLING_NETWORK"),
    ):
        await worker.tick()
        await drain(worker)
    result = (await client.get(path + "/billing/schedule")).json()["data"]["plan"]
    assert datetime.fromisoformat(result["next_due_at"]) - datetime.fromisoformat(
        result["updated_at"]
    ) == timedelta(hours=24)
    await due(credentials, run["study_id"])
    monkeypatch.setattr(credentials, "openai_billing_organization_id", "org-different")
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch", new_callable=AsyncMock
    ) as fetch:
        await worker.tick()
        await drain(worker)
        fetch.assert_not_awaited()
    result = (await client.get(path + "/billing/schedule")).json()["data"]
    assert (
        result["state"] == "attention" and result["plan"]["error_code"] == "BILLING_NOT_CONFIGURED"
    )


async def test_pause_and_changed_scope_cannot_be_overwritten_by_late_completion(
    client, credentials
):
    _, path = await prepare(client)
    started, release = asyncio.Event(), asyncio.Event()

    async def pending(*args):
        started.set()
        await release.wait()
        return lines()

    worker = BillingScheduler(credentials)
    with patch("app.services.study_billing_service.OpenAICostsClient.fetch", side_effect=pending):
        await worker.tick()
        await started.wait()
        await client.put(path + "/billing/schedule", json=plan(1, enabled=False))
        release.set()
        await drain(worker)
    result = (await client.get(path + "/billing/schedule")).json()["data"]
    assert result["state"] == "paused" and result["plan"]["last_attempt_id"] is None
    await client.put(path + "/billing/schedule", json=plan(2))
    await client.put(path + "/billing/config", json=config(1, project_id="proj_new"))
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch", new_callable=AsyncMock
    ) as fetch:
        await worker.tick()
        await drain(worker)
        fetch.assert_not_awaited()
    assert (await client.get(path + "/billing/schedule")).json()["data"]["state"] == "scope_changed"
    assert (await client.put(path + "/billing/schedule", json=plan(3))).status_code == 409
    assert (await client.put(path + "/billing/schedule", json=plan(3, 2))).status_code == 200


async def test_shutdown_cancels_owned_work_and_expired_claim_recovers(client, credentials):
    run, path = await prepare(client)
    started = asyncio.Event()

    async def pending(*args):
        started.set()
        await asyncio.Future()

    worker = BillingScheduler(credentials)
    with patch("app.services.study_billing_service.OpenAICostsClient.fetch", side_effect=pending):
        await worker.tick()
        await started.wait()
        await worker.stop()
    assert not worker.jobs
    result = (await client.get(path + "/billing")).json()["data"]
    assert result["latest_attempt"]["status"] == "interrupted"
    # Simulate a process killed before it could finalize its persistent claim.
    old = datetime.now(UTC) - timedelta(minutes=4)
    async with connect_sqlite(credentials.sqlite_path) as db:
        await db.execute(
            "UPDATE study_billing_attempts SET status='running',started_at=?,finished_at=NULL WHERE id=?",
            (old.isoformat(), result["latest_attempt"]["id"]),
        )
        await db.commit()
    await due(credentials, run["study_id"])
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines(),
    ) as fetch:
        fresh = BillingScheduler(credentials)
        await fresh.tick()
        await drain(fresh)
        fetch.assert_awaited_once()
    assert not (await client.get(path + "/billing")).json()["data"]["admission_blocked"]


async def test_disabling_worker_does_not_disable_budget_and_lifespan_stops_loop(
    client, credentials, monkeypatch
):
    run, path = await prepare(client)
    monkeypatch.setattr(credentials, "billing_scheduler_enabled", False)
    worker = BillingScheduler(credentials)
    await worker.tick()
    assert not worker.jobs
    with pytest.raises(AppError):
        await guard(credentials, run)
    assert not (await client.get(path + "/billing/schedule")).json()["data"]["worker_enabled"]
    monkeypatch.setattr(credentials, "billing_scheduler_enabled", True)
    monkeypatch.setattr(credentials, "mcp_http_enabled", False)
    started, stopped = asyncio.Event(), asyncio.Event()

    async def loop(self):
        started.set()
        try:
            await asyncio.Future()
        finally:
            stopped.set()

    with patch.object(BillingScheduler, "run", loop):
        app = create_app(credentials)
        async with app.router.lifespan_context(app):
            await started.wait()
        assert stopped.is_set()


async def test_worker_capacity_and_no_automatic_call_for_unconfigured_studies(client, credentials):
    studies = [await prepare(client) for _ in range(3)]
    started, release = asyncio.Event(), asyncio.Event()
    count = 0

    async def pending(*args):
        nonlocal count
        count += 1
        if count == 2:
            started.set()
        await release.wait()
        return lines()

    worker = BillingScheduler(credentials)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch", side_effect=pending
    ) as fetch:
        await worker.tick()
        await started.wait()
        assert len(worker.jobs) == 2 and fetch.await_count == 2
        release.set()
        await drain(worker)
        await worker.tick()
        await drain(worker)
        assert fetch.await_count == len(studies)


async def test_expired_attempt_cannot_replace_newer_snapshot_or_plan_state(client, credentials):
    run, path = await prepare(client)
    with patch(
        "app.services.study_billing_service.OpenAICostsClient.fetch",
        new_callable=AsyncMock,
        return_value=lines(),
    ):
        await sync(client, path)
    data = (await client.get(path + "/billing")).json()["data"]
    attempt = data["latest_attempt"]
    # A duplicate/late finalization must not mutate an already finalized attempt.
    async with connect_sqlite(credentials.sqlite_path) as db:
        changed = await StudyBillingService()._finish(db, attempt, "failed", "BILLING_NETWORK", [])
        assert not changed
    assert (await client.get(path + "/billing/schedule")).json()["data"]["state"] == "scheduled"
    await guard(credentials, run)
