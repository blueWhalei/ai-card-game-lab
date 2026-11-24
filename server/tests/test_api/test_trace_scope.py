"""Invocation diagnostics must expose scope, missing values and actual denominators."""

import aiosqlite
import pytest
from httpx import AsyncClient

from app.config import Settings
from app.repositories.trace_repo import TraceRepository
from tests.test_services.test_trace_list import _seed_game_and_traces


async def seed_scope(path: str) -> None:
    await _seed_game_and_traces(path)
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("DELETE FROM traces")
        repo = TraceRepository(db)
        cases = [
            *[{"response_time_ms": 100, "parser_ok": True} for _ in range(205)],
            {"response_time_ms": 0, "parser_ok": True},
            {"response_time_ms": 200, "parser_ok": False},
            {"response_time_ms": -1, "parser_ok": False},
            {"response_time_ms": "42", "parser_ok": "false"},
            {"response_time_ms": True, "parser_ok": 1},
            {"response_time_ms": None, "parser_ok": None},
            {},
        ]
        for index, metrics in enumerate(cases):
            await repo.create_trace(
                trace_id=f"record-{index:03}",
                game_id="game-exp",
                round_number=index,
                player_id="p1",
                model="fixture",
                prompt_version="v1",
                input_snapshot={},
                output_data={},
                metrics=metrics,
                created_at="2026-11-09T08:00:00+08:00",
            )
        for suffix, time in [("before", "2026-11-08T23:59:59Z"), ("after", "2026-11-09T01:00:01Z")]:
            await repo.create_trace(
                trace_id=suffix,
                game_id="game-exp",
                round_number=0,
                player_id="p1",
                model="fixture",
                prompt_version="v1",
                input_snapshot={},
                output_data={},
                metrics={"response_time_ms": 9000, "parser_ok": False},
                created_at=time,
            )


async def test_time_scoped_list_and_metrics_use_valid_denominators(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    await seed_scope(test_settings.sqlite_path)
    params = {
        "start_time": "2026-11-09T00:00:00Z",
        "end_time": "2026-11-09T09:00:00+08:00",
        "experiment_id": "exp-1",
        "game_id": "game-exp",
        "player_id": "p1",
        "model": "fixture",
    }
    first = await client.get("/api/v1/traces", params={**params, "page_size": 200})
    assert first.status_code == 200, first.text
    page = first.json()["data"]
    assert page["total"] == 212
    assert len(page["items"]) == 200
    second = (
        await client.get("/api/v1/traces", params={**params, "page_size": 200, "page": 2})
    ).json()["data"]
    ids = [row["id"] for row in page["items"] + second["items"]]
    assert ids == sorted(ids, reverse=True)
    assert len(set(ids)) == 212
    stats = await client.get("/api/v1/traces/metrics", params=params)
    assert stats.status_code == 200, stats.text
    assert stats.json()["data"] == {
        "total_traces": 212,
        "response_time_count": 207,
        "avg_response_time_ms": 100,
        "min_response_time_ms": 0,
        "max_response_time_ms": 200,
        "parser_success_count": 206,
        "parser_evaluated_count": 208,
    }
    failures = {**params, "parser_ok": "false"}
    assert (await client.get("/api/v1/traces", params=failures)).json()["data"]["total"] == 2
    assert (await client.get("/api/v1/traces/metrics", params=failures)).json()["data"][
        "parser_evaluated_count"
    ] == 2
    mismatch = {**params, "game_id": "game-other"}
    assert (await client.get("/api/v1/traces", params=mismatch)).json()["data"]["total"] == 0
    empty = (await client.get("/api/v1/traces/metrics", params=mismatch)).json()["data"]
    assert empty["response_time_count"] == empty["parser_evaluated_count"] == 0
    assert empty["avg_response_time_ms"] is None


@pytest.mark.parametrize("endpoint", ["/api/v1/traces", "/api/v1/traces/metrics"])
@pytest.mark.parametrize(
    "params",
    [
        {"start_time": "2026-11-09T00:00:00"},
        {"end_time": "invalid"},
        {"start_time": "2026-11-10T00:00:00Z", "end_time": "2026-11-09T00:00:00Z"},
    ],
)
async def test_invalid_time_windows_are_rejected(
    client: AsyncClient, endpoint: str, params: dict[str, str]
) -> None:
    assert (await client.get(endpoint, params=params)).status_code == 422


async def test_old_version_comparison_is_not_an_api_route(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    assert "/api/v1/traces/compare" not in schema["paths"]
    assert (await client.get("/api/v1/traces/compare")).status_code == 404
