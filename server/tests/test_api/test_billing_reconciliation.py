"""Cost evidence comparisons and review holds never certify complete costs or waive budgets."""

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.database import connect_sqlite
from app.migrations import migrate
from app.utils.exceptions import AppError
from tests.test_api.test_study_billing import config, guard, setup, sync
from tests.test_api.test_study_billing import credentials as credentials


async def fixture(client, limit="10"):
    run, path = await setup(client)
    today = datetime.now(UTC).date()
    start = today - timedelta(days=2)
    await client.put(
        path + "/billing/config", json=config(start_date=start.isoformat(), limit=limit)
    )

    async def costs(project, left, right):
        return [
            {
                "start_time": left,
                "end_time": left + 86400,
                "amount": "0.100000000000000001",
                "currency": "USD",
                "project_id": project,
                "line_item": "cost",
            },
            {
                "start_time": left,
                "end_time": left + 86400,
                "amount": "-0.000000000000000001",
                "currency": "USD",
                "project_id": project,
                "line_item": "adjustment",
            },
            {
                "start_time": left + 86400,
                "end_time": left + 172800,
                "amount": "0.3",
                "currency": "USD",
                "project_id": project,
                "line_item": "next day",
            },
        ]

    with patch("app.services.study_billing_service.OpenAICostsClient.fetch", side_effect=costs):
        response = await sync(client, path)
        assert response.status_code == 200
    body = {
        "attempt_id": response.json()["data"]["snapshot"]["id"],
        "source_type": "cost_export",
        "source_reference": "Synthetic cost export / project filter",
        "organization_id": "org-test",
        "project_id": "proj_test",
        "currency": "USD",
        "source_amount": "0.1",
        "period_start": start.isoformat(),
        "period_end": (start + timedelta(days=1)).isoformat(),
        "scope_note": "User-transcribed project cost subtotal; excludes organization-level costs",
    }
    return run, path, path + "/billing/reconciliations", body


async def saved(client, base, body, request_id="request"):
    preview = await client.post(base + "/preview", json=body)
    assert preview.status_code == 200, preview.text
    payload = {
        **body,
        "expected_preview_hash": preview.json()["data"]["preview_hash"],
        "request_id": request_id,
    }
    response = await client.post(base, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"], payload


async def policy(client, base, revision=0, enabled=True):
    response = await client.put(
        base + "/policy",
        json={"expected_revision": revision, "enabled": enabled, "reason": "Review hold"},
    )
    assert response.status_code == 200, response.text


async def test_exact_period_subtotal_and_immutable_user_evidence(client, credentials):
    _, path, base, body = await fixture(client)
    data = (await client.get(base)).json()["data"]
    assert data["policy"] is None and data["total"] == 0 and not data["admission_blocked"]
    row, payload = await saved(client, base, body)
    result = row["comparison"]
    assert result["result"] == "matched" and result["difference"] == "0.000000000000000000"
    assert (
        result["interface_amount"] == "0.100000000000000000" and result["included_line_count"] == 2
    )
    assert result["snapshot"]["amount"] == "0.400000000000000000"
    assert not row["pending"] and result["input"] == body
    assert (await client.post(base, json=payload)).json()["data"]["id"] == row["id"]
    assert (await client.post(base, json={**payload, "source_amount": "0.2"})).status_code == 409
    assert (await client.get(base)).json()["data"]["total"] == 1
    # No ledger addition and no request on historical read.
    with patch("app.services.study_billing_service.OpenAICostsClient.fetch") as fetch:
        detail = (await client.get(base + "/" + row["id"])).json()["data"]
        assert detail["comparison"] == result and detail["reviews"] == []
        fetch.assert_not_called()
    assert (await client.get(path + "/finance")).json()["data"]["total"] == 0


def csv_request(body, raw):
    return {
        **body,
        "source_amount": None,
        "csv": {
            "filename": "synthetic.csv",
            "content_base64": base64.b64encode(raw).decode(),
            "amount_column": "exact cost",
            "date_column": "service UTC",
            "project_column": "project",
            "currency_column": "currency",
        },
    }


async def test_csv_evidence_uses_exact_totals_and_saves_only_provenance(client, credentials):
    _, path, base, body = await fixture(client)
    day = body["period_start"]
    raw = (
        "service UTC,exact cost,project,currency,line item\r\n"
        f'{day},0.100000000000000001,proj_test,usd,"cost, detailed"\r\n'
        f'{day}T00:00:00Z,-0.000000000000000001,proj_test,USD,"adjustment\r\nsensitive fixture"\r\n'
    ).encode("utf-8-sig")
    request = csv_request(body, raw)
    columns = await client.post(
        base + "/csv-columns", json={"content_base64": request["csv"]["content_base64"]}
    )
    assert columns.json()["data"] == [
        "service UTC",
        "exact cost",
        "project",
        "currency",
        "line item",
    ]
    preview = (await client.post(base + "/preview", json=request)).json()["data"]
    assert preview["result"] == "matched"
    assert preview["input"]["source_amount"] == "0.100000000000000000"
    assert preview["difference"] == "0.000000000000000000"
    assert preview["csv_evidence"] == {
        "filename": "synthetic.csv",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "parser_version": "project-cost-csv-v1",
        "columns": {
            "amount": "exact cost",
            "date": "service UTC",
            "organization": None,
            "project": "project",
            "currency": "currency",
        },
        "row_count": 2,
        "first_service_date": day,
        "last_service_date": day,
    }
    assert (await client.get(base)).json()["data"]["total"] == 0
    changed = await client.post(
        base,
        json={
            **csv_request(body, raw + b"\r\n"),
            "expected_preview_hash": preview["preview_hash"],
            "request_id": "csv",
        },
    )
    assert changed.status_code == 409 and changed.json()["code"] == "RECONCILIATION_CHANGED"
    record, payload = await saved(client, base, request, request_id="csv")
    assert record["comparison"] == preview
    assert (await client.post(base, json=payload)).json()["data"]["id"] == record["id"]
    assert (await client.get(base)).json()["data"]["total"] == 1
    assert (await client.get(path + "/finance")).json()["data"]["total"] == 0
    async with connect_sqlite(credentials.sqlite_path) as db:
        cursor = await db.execute("SELECT comparison_json FROM billing_reconciliations")
        stored = (await cursor.fetchone())[0]
        assert "sensitive fixture" not in stored and "content_base64" not in stored


@pytest.mark.parametrize(
    "variant,code",
    [
        ("wrong_project", "RECONCILIATION_CSV_SCOPE"),
        ("wrong_currency", "RECONCILIATION_CSV_SCOPE"),
        ("exclusive_end", "RECONCILIATION_CSV_SCOPE"),
        ("duplicate_mapping", "RECONCILIATION_CSV_COLUMNS"),
        ("invalid_amount", "RECONCILIATION_CSV_INVALID"),
        ("missing_value", "RECONCILIATION_CSV_INVALID"),
        ("empty", "RECONCILIATION_CSV_INVALID"),
    ],
)
async def test_csv_invalid_rows_and_scope_are_not_silently_skipped(
    client, credentials, variant, code
):
    _, _, base, body = await fixture(client)
    header = "service UTC,exact cost,project,currency\n"
    day = body["period_end"] if variant == "exclusive_end" else body["period_start"]
    amount = "1e-4" if variant == "invalid_amount" else "0.1"
    project = "proj_other" if variant == "wrong_project" else "proj_test"
    currency = "EUR" if variant == "wrong_currency" else "USD"
    row = (
        f"{day},{amount},{project}"
        if variant == "missing_value"
        else f"{day},{amount},{project},{currency}"
    )
    request = csv_request(body, (header + ("" if variant == "empty" else row)).encode())
    if variant == "duplicate_mapping":
        request["csv"]["date_column"] = "exact cost"
    response = await client.post(base + "/preview", json=request)
    assert response.status_code == 422 and response.json()["code"] == code
    assert (await client.get(base)).json()["data"]["total"] == 0


async def test_invalid_csv_request_does_not_echo_file_bytes(client, credentials):
    _, _, base, body = await fixture(client)
    request = csv_request(body, b"Do not echo this file")
    del request["csv"]["date_column"]
    response = await client.post(base + "/preview", json=request)
    assert response.status_code == 422
    assert request["csv"]["content_base64"] not in response.text
    assert response.json()["detail"][0]["loc"][-1] == "date_column"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"source_type": "invoice_total"}, "basis"),
        ({"source_type": "payment_receipt"}, "basis"),
        ({"organization_id": "org-another"}, "organization"),
        ({"project_id": None}, "project"),
        ({"project_id": "proj_other"}, "project"),
        ({"currency": "CNY"}, "currency"),
    ],
)
async def test_incomparable_evidence_never_has_a_zero_difference(
    client, credentials, change, reason
):
    _, _, base, body = await fixture(client)
    row, _ = await saved(client, base, {**body, **change})
    result = row["comparison"]
    assert result["result"] == "not_comparable" and reason in result["reasons"]
    assert result["difference"] is None and result["interface_amount"] is None
    assert result["included_line_count"] is None and row["pending"]


async def test_period_coverage_and_crossing_buckets_are_not_prorated(client, credentials):
    _, _, base, body = await fixture(client)
    earlier = (datetime.fromisoformat(body["period_start"]) - timedelta(days=1)).date().isoformat()
    result = (await client.post(base + "/preview", json={**body, "period_start": earlier})).json()[
        "data"
    ]
    assert result["reasons"] == ["period"] and result["difference"] is None
    async with connect_sqlite(credentials.sqlite_path) as db:
        row = await (
            await db.execute(
                "SELECT items_json FROM study_billing_attempts WHERE id=?", (body["attempt_id"],)
            )
        ).fetchone()
        items = json.loads(row[0])
        items[0]["end_time"] += 1
        await db.execute(
            "UPDATE study_billing_attempts SET items_json=? WHERE id=?",
            (json.dumps(items), body["attempt_id"]),
        )
        await db.commit()
    result = (await client.post(base + "/preview", json=body)).json()["data"]
    assert result["reasons"] == ["bucket_boundary"] and result["difference"] is None


@pytest.mark.parametrize(
    "amount", [0.1, "NaN", "1e-3", "1000000000000", "0.0000000000000000001", True]
)
async def test_invalid_amount_is_rejected_without_coercion(client, credentials, amount):
    _, _, base, body = await fixture(client)
    assert (
        await client.post(base + "/preview", json={**body, "source_amount": amount})
    ).status_code == 422


async def test_closed_period_and_cross_study_source_validation(client, credentials):
    _, _, base, body = await fixture(client)
    for changes in [
        {"period_end": body["period_start"]},
        {"period_end": (datetime.now(UTC).date() + timedelta(days=1)).isoformat()},
        {"scope_note": " "},
        {"attempt_id": "missing"},
    ]:
        assert (await client.post(base + "/preview", json={**body, **changes})).status_code in (
            422,
            409,
        )
    _, other = await setup(client)
    assert (
        await client.post(other + "/billing/reconciliations/preview", json=body)
    ).status_code == 409
    assert (await client.get("/api/v1/studies/missing/billing/reconciliations")).status_code == 404


async def test_snapshot_change_and_concurrent_duplicate_save(client, credentials):
    _, _, base, body = await fixture(client)
    preview = (await client.post(base + "/preview", json=body)).json()["data"]
    payload = {**body, "expected_preview_hash": preview["preview_hash"], "request_id": "same"}
    responses = await asyncio.gather(
        client.post(base, json=payload), client.post(base, json=payload)
    )
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json()["data"]["id"] == responses[1].json()["data"]["id"]
    async with connect_sqlite(credentials.sqlite_path) as db:
        await db.execute(
            "UPDATE study_billing_attempts SET finished_at='changed' WHERE id=?",
            (body["attempt_id"],),
        )
        await db.commit()
    response = await client.post(base, json={**payload, "request_id": "new"})
    assert response.status_code == 409 and response.json()["code"] == "RECONCILIATION_CHANGED"
    assert (await client.get(base)).json()["data"]["total"] == 1


async def test_review_policy_blocks_before_execution_and_resolution_does_not_waive_costs(
    client, credentials
):
    run, path, base, body = await fixture(client)
    row, _ = await saved(client, base, {**body, "source_amount": "0.2"})
    assert row["comparison"]["difference"] == "-0.100000000000000000"
    await guard(credentials, run)  # Opt-in policy is off.
    await policy(client, base)
    with pytest.raises(AppError, match="Supplier cost") as exc:
        await guard(credentials, run)
    assert exc.value.code == "SUPPLIER_RECONCILIATION_PENDING"
    # Use the public collect path: no model or game is created.
    response = await client.post(f"/api/v1/experiments/{run['id']}/collect", json={"count": 1})
    assert (
        response.status_code == 409 and response.json()["code"] == "SUPPLIER_RECONCILIATION_PENDING"
    )
    state = (await client.get(path + "/billing")).json()["data"]
    assert (
        state["state"] == "below" and state["reconciliation_blocked"] and state["admission_blocked"]
    )
    review_path = base + "/" + row["id"] + "/reviews"
    assert (
        await client.post(
            review_path,
            json={
                "expected_revision": 0,
                "action": "resolve",
                "reason": "Difference traced to source rounding; original amounts retained",
            },
        )
    ).status_code == 200
    await guard(credentials, run)
    assert (
        await client.post(
            review_path, json={"expected_revision": 0, "action": "reopen", "reason": "stale"}
        )
    ).status_code == 409
    await client.post(
        review_path,
        json={
            "expected_revision": 1,
            "action": "reopen",
            "reason": "Further verification required",
        },
    )
    assert (await client.get(base)).json()["data"]["pending_count"] == 1
    # A configuration change cannot silently dispose of a previous discrepancy.
    await client.put(
        path + "/billing/config", json=config(1, enabled=False, project_id="proj_changed")
    )
    with pytest.raises(AppError) as exc:
        await guard(credentials, run)
    assert exc.value.code == "SUPPLIER_RECONCILIATION_PENDING"
    await client.post(
        review_path,
        json={"expected_revision": 2, "action": "resolve", "reason": "Documented disposition"},
    )
    await client.put(path + "/billing/config", json=config(2, limit="0"))
    with pytest.raises(AppError) as exc:
        await guard(credentials, run)
    assert exc.value.code == "SUPPLIER_BILLING_UNAVAILABLE"
    detail = (await client.get(base + "/" + row["id"])).json()["data"]
    assert [r["action"] for r in detail["reviews"]] == ["resolve", "reopen", "resolve"]
    assert detail["comparison"] == row["comparison"]


async def test_policy_conflict_void_audit_pagination_and_isolation(client, credentials):
    _, _, base, body = await fixture(client)
    row, _ = await saved(client, base, {**body, "source_type": "invoice_total"})
    await policy(client, base)
    assert (
        await client.put(
            base + "/policy", json={"expected_revision": 0, "enabled": False, "reason": "stale"}
        )
    ).status_code == 409
    review = base + "/" + row["id"] + "/reviews"
    await client.post(
        review,
        json={
            "expected_revision": 0,
            "action": "void",
            "reason": "Incorrect scope; retained for audit",
        },
    )
    assert (await client.get(base)).json()["data"]["pending_count"] == 0
    assert (
        await client.post(review, json={"expected_revision": 1, "action": "reopen", "reason": "no"})
    ).status_code == 409
    for i in range(11):
        await saved(client, base, body, str(i))
    data = (await client.get(base + "?page=2")).json()["data"]
    assert data["total"] == 12 and len(data["records"]) == 2
    _, other = await setup(client)
    assert (await client.get(other + "/billing/reconciliations/" + row["id"])).status_code == 404
    await policy(client, base, 1, False)
    assert len((await client.get(base)).json()["data"]["policy_history"]) == 2


async def test_v9_migration_preserves_snapshot_and_plan_defaults(client, credentials):
    _, path, _, body = await fixture(client)
    await client.put(
        path + "/billing/schedule",
        json={
            "expected_revision": 0,
            "expected_config_revision": 1,
            "enabled": False,
            "interval_minutes": 15,
            "reason": "Keep",
        },
    )
    async with connect_sqlite(credentials.sqlite_path) as db:
        for table in (
            "billing_reconciliation_reviews",
            "billing_reconciliations",
            "billing_reconciliation_policies",
        ):
            await db.execute("DROP TABLE " + table)
        await db.execute("PRAGMA user_version=9")
        await db.commit()
        assert await migrate(db) == 10 and await migrate(db) == 10
        row = await (
            await db.execute(
                "SELECT amount FROM study_billing_attempts WHERE id=?", (body["attempt_id"],)
            )
        ).fetchone()
        assert row[0] == "0.400000000000000000"
        assert (
            await (
                await db.execute("SELECT COUNT(*) FROM billing_reconciliation_policies")
            ).fetchone()
        )[0] == 0
        assert (
            await (
                await db.execute("SELECT enabled FROM study_billing_schedule_revisions")
            ).fetchone()
        )[0] == 0


async def test_resolved_difference_does_not_unlock_a_reached_cost_limit(client, credentials):
    run, path, base, body = await fixture(client, limit="0.4")
    row, _ = await saved(client, base, {**body, "source_amount": "0.2"})
    await policy(client, base)
    await client.post(
        base + "/" + row["id"] + "/reviews",
        json={
            "expected_revision": 0,
            "action": "resolve",
            "reason": "Disposition does not change cost cap",
        },
    )
    state = (await client.get(path + "/billing")).json()["data"]
    assert not state["reconciliation_blocked"] and state["cost_admission_blocked"]
    with pytest.raises(AppError) as exc:
        await guard(credentials, run)
    assert exc.value.code == "SUPPLIER_BUDGET_REACHED"


async def test_empty_snapshot_negative_amount_and_tampered_totals(client, credentials):
    _, path, base, body = await fixture(client)
    with patch("app.services.study_billing_service.OpenAICostsClient.fetch", return_value=[]):
        response = await sync(client, path)
    body["attempt_id"] = response.json()["data"]["snapshot"]["id"]
    result = (await client.post(base + "/preview", json={**body, "source_amount": "0"})).json()[
        "data"
    ]
    assert result["result"] == "matched" and result["included_line_count"] == 0
    result = (
        await client.post(
            base + "/preview",
            json={
                **body,
                "source_amount": "-0.000000000000000001",
                "source_type": "invoice_project_subtotal",
            },
        )
    ).json()["data"]
    assert result["difference"] == "0.000000000000000001" and result["result"] == "difference"
    async with connect_sqlite(credentials.sqlite_path) as db:
        await db.execute(
            "UPDATE study_billing_attempts SET amount='1' WHERE id=?", (body["attempt_id"],)
        )
        await db.commit()
    response = await client.post(base + "/preview", json=body)
    assert response.status_code == 409 and response.json()["code"] == "RECONCILIATION_SOURCE"
