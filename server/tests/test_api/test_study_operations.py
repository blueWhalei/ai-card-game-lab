"""Current task status and observed usage: scope, missingness and paging."""

import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.game_repo import GameRepository
from app.repositories.trace_repo import TraceRepository
from tests.test_api.test_studies import create_run


@pytest.fixture
async def operations(client: AsyncClient, test_settings: Settings):
    run = await create_run(client)
    empty = await create_run(client, study_id=run["study_id"])
    outside = await create_run(client)
    now = datetime.now(UTC).isoformat()
    async with connect_sqlite(test_settings.sqlite_path) as db:
        for index, status in enumerate(
            [
                "created",
                "pending",
                "running",
                "paused",
                "finished",
                "failed",
                "interrupted",
                "cancelled",
                "unexpected",
            ]
        ):
            await GameRepository(db).create(
                f"g{index}",
                "doudizhu",
                ["p1", "p2", "p3"],
                "test",
                now,
                status=status,
                experiment_id=run["id"],
            )
        await db.execute("UPDATE games SET winner_role='no_bid' WHERE id='g4'")
        await db.commit()
        records = [
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": None},
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            {"prompt_tokens": "5", "completion_tokens": -1, "total_tokens": True},
            {},
            {},
            {"prompt_tokens": 2.5, "completion_tokens": 2**53, "total_tokens": 10},
            {"prompt_tokens": 4, "completion_tokens": None, "total_tokens": 12},
        ]
        repo = TraceRepository(db)
        for index, metrics in enumerate(records):
            await repo.create_trace(
                f"tr{index}", "g5", 0, "p1", "fixture", "v1", {}, {}, metrics, now
            )
        await repo.create_span("span", "tr0", "llm", now, now, "ok", {"total_tokens": 999})
        await repo.create_trace(
            "orphan", "absent", 0, "p1", "fixture", "v1", {}, {}, {"total_tokens": 999}, now
        )
        await GameRepository(db).create(
            "outside", "doudizhu", [], "test", now, experiment_id=outside["id"]
        )
        await repo.create_trace(
            "outside-trace", "outside", 0, "p1", "fixture", "v1", {}, {}, {"total_tokens": 999}, now
        )
        await db.execute("UPDATE traces SET metrics='broken-json' WHERE id='tr4'")
        await db.commit()
    return run, empty, f"/api/v1/studies/{run['study_id']}/operations"


async def test_status_counts_and_usage_keep_denominators_and_scope(client: AsyncClient, operations):
    run, empty, path = operations
    response = await client.get(path)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["study_id"] == run["study_id"] and data["total"] == 2
    assert datetime.fromisoformat(data["read_at"]).tzinfo is not None
    row = next(item for item in data["items"] if item["id"] == run["id"])
    assert row["game_count"] == 9 and row["target_games"] == 2
    assert row["states"] == {
        "waiting": 2,
        "running": 1,
        "paused": 1,
        "finished": 1,
        "failed": 1,
        "interrupted": 1,
        "cancelled": 1,
        "unknown": 1,
    }
    assert row["no_bid_count"] == 1 and row["trace_count"] == 7
    assert row["usage"] == {
        "prompt_tokens": {
            "value": 14,
            "recorded_count": 3,
            "missing_count": 1,
            "invalid_count": 3,
            "overflow": False,
        },
        "completion_tokens": {
            "value": 5,
            "recorded_count": 2,
            "missing_count": 2,
            "invalid_count": 3,
            "overflow": False,
        },
        "total_tokens": {
            "value": 22,
            "recorded_count": 3,
            "missing_count": 2,
            "invalid_count": 2,
            "overflow": False,
        },
    }
    absent = next(item for item in data["items"] if item["id"] == empty["id"])
    assert absent["game_count"] == absent["trace_count"] == 0
    assert absent["usage"]["total_tokens"]["value"] is None
    assert all(value == 0 for value in absent["states"].values())
    for state in ("active", "attention"):
        filtered = (await client.get(path, params={"state": state})).json()["data"]
        assert filtered["state"] == state and [item["id"] for item in filtered["items"]] == [
            run["id"]
        ]


@pytest.mark.parametrize("value", [None, 0, 2**53 - 1, 2**63 - 1])
async def test_missing_zero_and_unsafe_totals(
    client: AsyncClient, operations, test_settings: Settings, value
):
    run, _, path = operations
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute(
            "UPDATE traces SET metrics=? WHERE game_id='g5'", (json.dumps({"total_tokens": value}),)
        )
        await db.commit()
    data = (await client.get(path)).json()["data"]
    field = next(item for item in data["items"] if item["id"] == run["id"])["usage"]["total_tokens"]
    if value is None:
        assert field["value"] is None and field["missing_count"] == 7
    elif value == 0:
        assert field["value"] == 0 and field["recorded_count"] == 7
    elif value == 2**53 - 1:
        assert field["value"] is None and field["overflow"] and field["recorded_count"] == 7
    else:
        assert field["value"] is None and not field["overflow"] and field["invalid_count"] == 7


async def test_filter_before_pagination_and_deleted_membership(
    client: AsyncClient, operations, test_settings: Settings
):
    run, empty, path = operations
    async with connect_sqlite(test_settings.sqlite_path) as db:
        for index in range(23):
            rid = f"page-{index:02d}"
            await db.execute(
                "INSERT INTO experiments (id,name,game_type,player_ids,created_at,updated_at) VALUES (?,?,'doudizhu','[]','2099','2099')",
                (rid, rid),
            )
            await db.execute(
                "INSERT INTO study_runs (study_id,experiment_id) VALUES (?,?)",
                (run["study_id"], rid),
            )
        await db.commit()
    first = (await client.get(path)).json()["data"]
    second = (await client.get(path, params={"page": 2})).json()["data"]
    assert first["total"] == second["total"] == 25
    assert len(first["items"]) == 20 and len(second["items"]) == 5
    assert not ({r["id"] for r in first["items"]} & {r["id"] for r in second["items"]})
    assert (await client.get(path, params={"state": "attention"})).json()["data"]["total"] == 1
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute("DELETE FROM study_runs WHERE experiment_id=?", (run["id"],))
        await db.commit()
    assert (await client.get(path, params={"state": "attention"})).json()["data"]["items"] == []
    for params in ({"state": "bogus"}, {"page": 0}, {"page": 1000001}):
        assert (await client.get(path, params=params)).status_code == 422
    assert (await client.get("/api/v1/studies/missing/operations")).status_code == 404
