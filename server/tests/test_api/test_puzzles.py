"""HTTP tests for puzzle extract / list / run."""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient

from app.database import connect_sqlite
from app.repositories.experiment_repo import ExperimentRepository


async def test_extract_empty_list_and_run(client: AsyncClient, tmp_path) -> None:
    now = datetime.now(tz=UTC).isoformat()
    async with connect_sqlite(str(tmp_path / "test.db")) as db:
        await ExperimentRepository(db).create(
            experiment_id="exp-api-empty",
            name="api empty",
            notes="",
            game_type="doudizhu",
            player_ids=["p1", "p2", "p3"],
            target_games=1,
            created_at=now,
            updated_at=now,
        )

    extract = await client.post(
        "/api/v1/puzzles/extract",
        json={"experiment_id": "exp-api-empty", "min_spread": 0.0},
    )
    assert extract.status_code == 200
    body = extract.json()
    assert body["code"] == 0
    pack_id = body["data"]["pack_id"]
    assert body["data"]["puzzle_count"] == 0

    listed = await client.get("/api/v1/puzzles/packs")
    assert listed.status_code == 200
    packs = listed.json()["data"]
    assert any(p["pack_id"] == pack_id for p in packs)

    detail = await client.get(f"/api/v1/puzzles/packs/{pack_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["manifest"]["puzzle_count"] == 0
    assert detail.json()["data"]["preview"] == []

    run = await client.post(
        f"/api/v1/puzzles/packs/{pack_id}/run",
        json={"baseline_kind": "first"},
    )
    assert run.status_code == 200
    summary = run.json()["data"]["summary"]
    assert summary["n"] == 0
    assert summary["accuracy"] == 0.0


async def test_pack_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/puzzles/packs/does-not-exist")
    assert response.status_code == 404


async def test_probe_empty_pack(client: AsyncClient, tmp_path) -> None:
    now = datetime.now(tz=UTC).isoformat()
    async with connect_sqlite(str(tmp_path / "test.db")) as db:
        await ExperimentRepository(db).create(
            experiment_id="exp-api-probe",
            name="api probe",
            notes="",
            game_type="doudizhu",
            player_ids=["p1", "p2", "p3"],
            target_games=1,
            created_at=now,
            updated_at=now,
        )

    extract = await client.post(
        "/api/v1/puzzles/extract",
        json={"experiment_id": "exp-api-probe"},
    )
    pack_id = extract.json()["data"]["pack_id"]

    probe = await client.post(
        f"/api/v1/puzzles/packs/{pack_id}/probe",
        json={"baseline_kind": "first", "n_trials": 2},
    )
    assert probe.status_code == 200
    summary = probe.json()["data"]["summary"]
    assert summary["n"] == 0
    assert summary["consistency"] == 0.0
    assert summary["n_trials"] == 2
