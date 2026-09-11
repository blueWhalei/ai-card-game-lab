"""Research revision integrity through the public API."""

from __future__ import annotations

import aiosqlite
from httpx import AsyncClient

from app.config import Settings
from app.repositories.comparison_repo import ComparisonRepository


async def test_research_evidence_is_scoped_frozen_and_append_only(
    client: AsyncClient, test_settings: Settings
) -> None:
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute(
            "INSERT INTO games (id,game_type,status,player_ids,data_file,created_at) VALUES ('g','doudizhu','finished','[]','g.jsonl','2026-01-01')"
        )
        for decision_id, created_at in [("d", "2026-01-01"), ("future", "2099-01-01")]:
            await db.execute(
                "INSERT INTO decision_points (id,game_id,round_number,player_id,hand_cards,game_phase,legal_actions,chosen_action,created_at) VALUES (?, 'g',1,'p','[]','playing','[]','{}',?)",
                (decision_id, created_at),
            )
        await db.commit()
        snapshot = await ComparisonRepository(db).create(
            "cmp",
            "Comparison",
            "2026-02-01",
            {"computed_at": "2026-02-01", "experiments": [{"id": "e", "game_ids": ["g"]}]},
        )
    root = "/api/v1/experiments"
    base = f"{root}/comparisons/cmp"
    candidates = await client.get(f"{base}/decisions")
    assert candidates.status_code == 200
    assert [item["id"] for item in candidates.json()["data"]["items"]] == ["d"]
    draft = {
        "expected_revision": 0,
        "observations": "Observed",
        "interpretation": "Possible cause",
        "limitations": "One game",
        "evidence": [{"decision_id": "d", "note": "An example"}],
    }
    for invalid in (
        [{"decision_id": "future"}],
        [{"decision_id": "missing"}],
        [{"decision_id": "d"}, {"decision_id": "d"}],
    ):
        response = await client.post(f"{base}/conclusions", json={**draft, "evidence": invalid})
        assert response.status_code == 422
    saved = await client.post(f"{base}/conclusions", json=draft)
    assert saved.status_code == 201, saved.text
    data = saved.json()["data"]
    revision_id = data["record"]["id"]
    assert data["record"]["revision"] == 1
    assert data["evidence_status"] == {"d": "available"}
    conflict = await client.post(f"{base}/conclusions", json=draft)
    assert conflict.status_code == 409
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("UPDATE decision_points SET annotation='updated' WHERE id='d'")
        await db.commit()
    changed = (await client.get(f"{root}/conclusions/{revision_id}")).json()["data"]
    assert changed["record"] == data["record"]
    assert changed["evidence_status"] == {"d": "changed"}
    second = await client.post(
        f"{base}/conclusions",
        json={
            **draft,
            "expected_revision": 1,
            "observations": "Updated observation",
            "evidence": [],
        },
    )
    assert second.status_code == 201
    assert second.json()["data"]["record"]["revision"] == 2
    versions = (await client.get(f"{base}/conclusions?limit=1&offset=1")).json()["data"]
    assert [v["revision"] for v in versions] == [1]
    async with aiosqlite.connect(test_settings.sqlite_path) as db:
        await db.execute("DELETE FROM decision_points WHERE id='d'")
        await db.commit()
    report = (await client.get(f"{root}/conclusions/{revision_id}/export")).json()["data"]
    assert report["comparison"] == snapshot
    assert report["record"] == data["record"]
    assert report["evidence_status"] == {"d": "missing"}
    assert report["kind"] == "cardlab.research_report"
    for path in (
        "comparisons/missing/decisions",
        "comparisons/missing/conclusions",
        "conclusions/missing",
        "conclusions/missing/export",
    ):
        assert (await client.get(f"{root}/{path}")).status_code == 404
    assert (
        await client.post(f"{base}/conclusions", json={**draft, "observations": "  "})
    ).status_code == 422
