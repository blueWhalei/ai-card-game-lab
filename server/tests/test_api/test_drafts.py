"""Draft restoration, validation and concurrent writes through the public API."""

import asyncio

import aiosqlite
import pytest
from httpx import AsyncClient

from app.config import Settings
from app.database import init_db
from app.repositories.comparison_repo import ComparisonRepository


@pytest.mark.parametrize("kind", ["experiment", "comparison"])
async def test_draft_restores_and_rejects_stale_writes(
    client: AsyncClient, test_settings: Settings, kind: str
) -> None:
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute(
            "INSERT INTO experiments (id,name,game_type,player_ids,created_at,updated_at) VALUES ('owner','Run','doudizhu','[]','2026','2026')"
        )
        await ComparisonRepository(db).create("owner", "Comparison", "2026", {})
        await db.commit()
    path = f"/api/v1/drafts/{kind}/owner"
    initial = (await client.get(path)).json()["data"]
    assert initial["revision"] == 0 and initial["updated_at"] is None
    content = initial["content"]
    field = "notes" if kind == "experiment" else "observations"
    content[field] = "尚未完成的研究笔记\nwith unicode and whitespace  "
    request = {"expected_revision": 0, "content": content}
    # Both windows started from the same revision. Exactly one can write.
    results = await asyncio.gather(client.put(path, json=request), client.put(path, json=request))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert next(r for r in results if r.status_code == 409).json()["code"] == "DRAFT_CONFLICT"
    await init_db(test_settings.sqlite_path)
    restored = (await client.get(path)).json()["data"]
    assert restored["content"] == content
    assert restored["revision"] == 1 and restored["updated_at"]
    content[field] = "Revised"
    assert (
        await client.put(path, json={"expected_revision": 1, "content": content})
    ).status_code == 200
    # Autosave must never publish a research conclusion or change applied notes.
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        assert (await (await db.execute("SELECT COUNT(*) FROM research_revisions")).fetchone())[
            0
        ] == 0
        assert (
            await (await db.execute("SELECT notes FROM experiments WHERE id='owner'")).fetchone()
        )[0] == ""
    assert (await client.get(f"/api/v1/drafts/{kind}/missing")).status_code == 404
    assert (await client.put(f"/api/v1/drafts/{kind}/missing", json=request)).status_code == 404
    invalid = {**content, "unknown_field": True}
    assert (
        await client.put(path, json={"expected_revision": 2, "content": invalid})
    ).status_code == 422
    assert (await client.get(path)).json()["data"]["revision"] == 2
    if kind == "experiment":
        stale = await client.patch(
            "/api/v1/experiments/owner",
            json={"expected_draft_revision": 1, "notes": "stale applied text"},
        )
        assert stale.status_code == 409
        applied = await client.patch(
            "/api/v1/experiments/owner",
            json={"expected_draft_revision": 2, "notes": "Revised"},
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["data"]["notes"] == "Revised"


async def test_draft_rejects_mismatched_scope(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/drafts/comparison/owner",
        json={
            "expected_revision": 0,
            "content": {
                "kind": "experiment",
                "hypothesis": "",
                "notes": "",
                "conclusion": "",
                "tags_input": "",
            },
        },
    )
    assert response.status_code == 422
