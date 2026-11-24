"""Research organization boundaries through the public API, without model calls."""

import asyncio

import aiosqlite
from httpx import AsyncClient

from app.config import Settings
from app.database import init_db

PLAYERS = ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"]


async def create_run(client: AsyncClient, **extra: object) -> dict:
    response = await client.post(
        "/api/v1/experiments",
        json={
            "name": "Run",
            "player_ids": PLAYERS,
            "target_games": 2,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def create_study(client: AsyncClient, title: str = "Research") -> dict:
    response = await client.post("/api/v1/studies", json={"title": title, "question": "Why?"})
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_quick_run_clone_and_control_share_research(client: AsyncClient) -> None:
    run = await create_run(client, hypothesis="A testable question")
    study_id = run["study_id"]
    control = await create_run(client, pair_deals=True, source_experiment_id=run["id"])
    clone = await client.post(f"/api/v1/experiments/{run['id']}/clone", json={})
    assert clone.status_code == 201, clone.text
    assert control["study_id"] == clone.json()["data"]["study_id"] == study_id
    detail = (await client.get(f"/api/v1/studies/{study_id}")).json()["data"]
    assert detail["question"] == "A testable question"
    assert len(detail["runs"]) == 3
    listed = (await client.get("/api/v1/studies")).json()["data"]
    assert len(listed) == 1 and listed[0]["run_count"] == 3


async def test_study_persistence_validation_and_isolation(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    first = await create_study(client, "  中文研究  ")
    second = await create_study(client, "Separate")
    run = await create_run(client, study_id=first["id"])
    await init_db(test_settings.sqlite_path)
    restored = (await client.get(f"/api/v1/studies/{first['id']}")).json()["data"]
    assert restored["title"] == "中文研究"
    assert [r["id"] for r in restored["runs"]] == [run["id"]]
    assert (await client.get(f"/api/v1/studies/{second['id']}")).json()["data"]["runs"] == []
    assert (await client.get("/api/v1/studies/missing")).status_code == 404
    for body in ({"title": "  "}, {"title": "valid", "unknown": True}):
        assert (await client.post("/api/v1/studies", json=body)).status_code == 422
    page1 = (await client.get("/api/v1/studies?limit=1")).json()["data"]
    page2 = (await client.get("/api/v1/studies?limit=1&offset=1")).json()["data"]
    assert len(page1) == len(page2) == 1 and page1[0]["id"] != page2[0]["id"]


async def test_invalid_research_creation_leaves_no_run(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/experiments",
        json={
            "name": "No orphan",
            "player_ids": PLAYERS,
            "study_id": "missing",
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "STUDY_NOT_FOUND"
    assert (await client.get("/api/v1/experiments")).json()["data"] == []
    assert (await client.get("/api/v1/studies")).json()["data"] == []


async def test_attachment_is_idempotent_and_never_moves_runs(client: AsyncClient) -> None:
    run = await create_run(client)
    other = await create_study(client)
    body = {"experiment_id": run["id"]}
    same = f"/api/v1/studies/{run['study_id']}/runs"
    assert (await client.post(same, json=body)).status_code == 200
    assert (await client.post(same, json=body)).status_code == 200
    conflict = await client.post(f"/api/v1/studies/{other['id']}/runs", json=body)
    assert conflict.status_code == 409 and conflict.json()["code"] == "STUDY_RUN_CONFLICT"
    assert (await client.post(same, json={"experiment_id": "missing"})).status_code == 404
    assert (await client.post("/api/v1/studies/missing/runs", json=body)).status_code == 404
    control = await client.post(
        "/api/v1/experiments",
        json={
            "name": "Wrong scope",
            "player_ids": PLAYERS,
            "pair_deals": True,
            "source_experiment_id": run["id"],
            "study_id": other["id"],
        },
    )
    assert control.status_code == 409


async def test_concurrent_attachment_has_one_owner(
    client: AsyncClient, test_settings: Settings
) -> None:
    a, b = await create_study(client, "A"), await create_study(client, "B")
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute(
            "INSERT INTO experiments (id,name,game_type,player_ids,created_at,updated_at) VALUES ('unassigned','Run','doudizhu','[]','2026','2026')"
        )
        await db.commit()
    responses = await asyncio.gather(
        *[
            client.post(f"/api/v1/studies/{s['id']}/runs", json={"experiment_id": "unassigned"})
            for s in (a, b)
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    owner = (await client.get("/api/v1/experiments/unassigned")).json()["data"]["study_id"]
    assert owner in {a["id"], b["id"]}


async def test_records_include_only_comparisons_wholly_within_research(client: AsyncClient) -> None:
    a = await create_run(client)
    b = await create_run(client, study_id=a["study_id"])
    outside = await create_run(client)

    async def snapshot(ids: list[str]) -> dict:
        response = await client.post(
            "/api/v1/experiments/comparisons",
            json={
                "title": "Comparison",
                "experiment_ids": ids,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]

    inside = await snapshot([a["id"], b["id"]])
    await snapshot([a["id"], outside["id"]])
    published = await client.post(
        f"/api/v1/experiments/comparisons/{inside['id']}/conclusions",
        json={
            "expected_revision": 0,
            "observations": "No games yet",
            "limitations": "No evidence",
        },
    )
    assert published.status_code == 201, published.text
    records = (await client.get(f"/api/v1/studies/{a['study_id']}")).json()["data"]["comparisons"]
    assert len(records) == 1 and records[0]["id"] == inside["id"]
    assert records[0]["revision_count"] == 1
