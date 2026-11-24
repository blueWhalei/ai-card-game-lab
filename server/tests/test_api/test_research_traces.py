"""Recorded invocation citations: scope, atomic publication and immutable evidence."""

import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.comparison_repo import ComparisonRepository
from app.repositories.trace_repo import TraceRepository
from tests.test_services.test_trace_list import _seed_game_and_traces

BASE = "/api/v1/experiments/comparisons/cmp"
TARGETS = "/api/v1/experiments/evidence/traces/tr-exp-p1/comparisons"


@pytest.fixture
async def citation(client: AsyncClient, test_settings: Settings):
    await _seed_game_and_traces(test_settings.sqlite_path)
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute("UPDATE games SET metadata = ? WHERE id='game-exp'", ('{"deal_seed":42}',))
        await db.execute(
            "UPDATE traces SET metrics = ?", ('{"parser_ok":true,"response_time_ms":0}',)
        )
        await db.commit()
        await TraceRepository(db).create_span(
            "span",
            "tr-exp-p1",
            "llm",
            datetime.now(UTC).isoformat(),
            None,
            "ok",
            {"text": "Recorded output <script>never execute</script>"},
        )
        result = {
            "metric_version": "paired-cohort-v5",
            "computed_at": datetime.now(UTC).isoformat(),
            "experiments": [
                {
                    "id": "exp-1",
                    "game_ids": ["game-exp"],
                    "game_type": "doudizhu",
                    "player_ids": ["p1", "p2", "p3"],
                }
            ],
            "coverage": {"members": [{"seed": 42, "game_ids": {"exp-1": "game-exp"}}]},
        }
        await ComparisonRepository(db).create(
            "cmp", "Synthetic invocation evidence", result["computed_at"], result
        )
    response = await client.get(f"{BASE}/traces/tr-exp-p1")
    assert response.status_code == 200, response.text
    preview = response.json()["data"]
    draft = {
        "expected_revision": 0,
        "observations": "Recorded invocation",
        "interpretation": "",
        "limitations": "Diagnostic only; no additional independent samples",
        "evidence": [],
        "trace_evidence": [
            {
                "trace_id": "tr-exp-p1",
                "expected_source_hash": preview["source_hash"],
                "note": "  Selected record  ",
            }
        ],
    }
    return preview, draft, result


async def test_trace_freezes_body_and_survives_changed_invalid_and_missing_sources(
    client: AsyncClient, citation, test_settings: Settings
):
    preview, draft, result = citation
    targets = (await client.get(TARGETS)).json()["data"]
    assert targets["source_hash"] == preview["source_hash"]
    assert [row["id"] for row in targets["items"]] == ["cmp"]
    response = await client.post(f"{BASE}/conclusions", json=draft)
    assert response.status_code == 201, response.text
    record = response.json()["data"]["record"]
    saved = record["trace_evidence"][0]
    assert saved["trace"] == preview["trace"] and saved["source"] == preview["source"]
    assert saved["note"] == "Selected record"
    assert response.json()["data"]["trace_evidence_status"] == {"tr-exp-p1": "available"}
    endpoint = f"/api/v1/experiments/conclusions/{record['id']}/export"
    mutations = [
        ("UPDATE spans SET data = '{\"edited\":true}'", "changed"),
        (
            "UPDATE games SET metadata = '{\"deal_seed\":43}' WHERE id='game-exp'",
            "identity_mismatch",
        ),
        ("UPDATE traces SET metrics = 'invalid-json' WHERE id='tr-exp-p1'", "invalid"),
        ("DELETE FROM traces WHERE id='tr-exp-p1'", "missing"),
    ]
    for sql, status in mutations:
        async with connect_sqlite(test_settings.sqlite_path) as db:
            if status == "missing":
                await db.execute("DELETE FROM spans WHERE trace_id='tr-exp-p1'")
            await db.execute(sql)
            await db.commit()
        response = await client.get(endpoint)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["record"] == record
        assert data["trace_evidence_status"] == {"tr-exp-p1": status}
        assert data["comparison"]["result"]["coverage"] == result["coverage"]


@pytest.mark.parametrize(
    "change",
    [
        "seed",
        "owner",
        "player",
        "cohort",
        "version",
        "cutoff",
        "span_time",
        "naive_time",
        "payload",
    ],
)
async def test_scope_or_invalid_source_never_publishes(
    client: AsyncClient, citation, test_settings: Settings, change: str
):
    _, draft, result = citation
    async with connect_sqlite(test_settings.sqlite_path) as db:
        if change == "seed":
            await db.execute("UPDATE games SET metadata = '{\"deal_seed\":7}' WHERE id='game-exp'")
        elif change == "owner":
            await db.execute(
                "INSERT INTO experiments (id,name,game_type,player_ids,created_at,updated_at) VALUES ('wrong','Other','doudizhu','[]','2026','2026')"
            )
            await db.execute("UPDATE games SET experiment_id = 'wrong' WHERE id='game-exp'")
        elif change == "player":
            await db.execute("UPDATE traces SET player_id = 'outsider' WHERE id='tr-exp-p1'")
        elif change == "span_time":
            await db.execute("UPDATE spans SET end_time = '2099-01-01T00:00:00Z'")
        elif change == "naive_time":
            await db.execute(
                "UPDATE traces SET created_at = '2026-01-01T00:00:00' WHERE id='tr-exp-p1'"
            )
        elif change == "payload":
            await db.execute("UPDATE traces SET metrics = '{\"latency\":NaN}' WHERE id='tr-exp-p1'")
        else:
            if change == "cohort":
                result["coverage"]["members"] = []
            elif change == "version":
                result["metric_version"] = "legacy"
            else:
                result["computed_at"] = "2000-01-01T00:00:00Z"
            await db.execute("UPDATE comparison_snapshots SET result = ?", (json.dumps(result),))
        await db.commit()
    preview = await client.get(f"{BASE}/traces/tr-exp-p1")
    assert preview.status_code == 422, preview.text
    response = await client.post(f"{BASE}/conclusions", json=draft)
    assert response.status_code == 422, response.text
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []


async def test_changed_hash_keeps_draft_and_requires_explicit_refresh(
    client: AsyncClient, citation, test_settings: Settings
):
    _, draft, _ = citation
    path = "/api/v1/drafts/comparison/cmp"
    content = (await client.get(path)).json()["data"]["content"]
    content.update(draft)
    saved_draft = await client.put(path, json={"expected_revision": 0, "content": content})
    assert saved_draft.status_code == 200, saved_draft.text
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute("UPDATE spans SET data = '{\"changed\":true}'")
        await db.commit()
    response = await client.post(f"{BASE}/conclusions", json=draft)
    assert response.status_code == 409 and response.json()["code"] == "RESEARCH_TRACE_CHANGED"
    assert (await client.get(path)).json()["data"] == saved_draft.json()["data"]
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []
    refreshed = (await client.get(f"{BASE}/traces/tr-exp-p1")).json()["data"]
    draft["trace_evidence"][0]["expected_source_hash"] = refreshed["source_hash"]
    assert (await client.post(f"{BASE}/conclusions", json=draft)).status_code == 201


@pytest.mark.parametrize("limit", ["duplicate", "count", "record", "total"])
async def test_citation_limits_are_atomic(client: AsyncClient, citation, monkeypatch, limit: str):
    _, draft, _ = citation
    if limit in ("duplicate", "count"):
        draft["trace_evidence"] *= 2 if limit == "duplicate" else 6
    else:
        monkeypatch.setattr(
            f"app.services.research_traces.MAX_{'TRACE' if limit == 'record' else 'TOTAL'}_BYTES",
            10,
        )
    response = await client.post(f"{BASE}/conclusions", json=draft)
    assert response.status_code == 422, response.text
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []


async def test_discovery_paginates_filtered_candidates_and_compares_absolute_time(
    client: AsyncClient, citation, test_settings: Settings
):
    preview, _, result = citation
    # Equivalent offset timestamp is compared as an instant, not as text.
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await db.execute(
            "UPDATE traces SET created_at='2026-01-01T09:00:00+09:00' WHERE id='tr-exp-p1'"
        )
        await db.commit()
        result["computed_at"] = "2026-01-01T00:00:01Z"
        # Game/spans must also precede the cutoff.
        await db.execute("UPDATE games SET created_at='2026-01-01T00:00:00Z'")
        await db.execute("UPDATE spans SET start_time='2026-01-01T00:00:00Z'")
        await db.commit()
        repo = ComparisonRepository(db)
        for index in range(21):
            copy = deepcopy(result)
            if index:
                copy["experiments"][0]["player_ids"] = ["different"]
            await repo.create(f"extra-{index:02d}", "Candidate", f"2099-{index:02d}", copy)
    first = (await client.get(TARGETS)).json()["data"]
    assert first["items"] == [] and first["next_offset"] == 20
    second = (await client.get(TARGETS, params={"offset": 20})).json()["data"]
    assert {row["id"] for row in second["items"]} == {"cmp", "extra-00"}
    assert second["next_offset"] is None
    assert len(second["source_hash"]) == len(preview["source_hash"]) == 64


async def test_exact_trace_detail_respects_all_active_filters(client: AsyncClient, citation):
    path = "/api/v1/traces/tr-exp-p1"
    filters = {
        "game_id": "game-exp",
        "experiment_id": "exp-1",
        "player_id": "p1",
        "model": "model-a",
        "parser_ok": "true",
    }
    response = await client.get(path, params=filters)
    assert response.status_code == 200 and len(response.json()["data"]["spans"]) == 1
    for key, value in {
        "game_id": "game-other",
        "experiment_id": "other",
        "player_id": "p2",
        "model": "model-b",
        "parser_ok": "false",
    }.items():
        assert (await client.get(path, params={**filters, key: value})).status_code == 404
