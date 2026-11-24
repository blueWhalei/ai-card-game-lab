"""Published diagnostic citations freeze verified sources within the comparison cohort."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.core.eval.puzzle import load_pack, save_pack
from app.core.eval.puzzle_results import pack_fingerprint, pack_snapshot
from app.database import connect_sqlite
from app.repositories.comparison_repo import ComparisonRepository
from tests.test_api.test_decision_puzzles import seed_source

BASE = "/api/v1/experiments/comparisons/cmp"


@pytest.fixture
async def citation(client: AsyncClient, test_settings: Settings):
    await seed_source(test_settings.sqlite_path)
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await ComparisonRepository(db).create(
            "cmp",
            "Synthetic diagnostic citation",
            datetime.now(UTC).isoformat(),
            {
                "computed_at": datetime.now(UTC).isoformat(),
                "experiments": [{"id": "source-run", "game_ids": ["source-game"]}],
                "coverage": {"members": [{"seed": 42, "game_ids": {"source-run": "source-game"}}]},
            },
        )
    source = (await client.get("/api/v1/puzzles/decisions/source-d2")).json()["data"]
    pack = (
        await client.post(
            "/api/v1/puzzles/from-decision",
            json={
                "decision_id": "source-d2",
                "question": "Synthetic order diagnostic",
                "expected_source_hash": source["source_hash"],
            },
        )
    ).json()["data"]
    report = (
        await client.post(
            f"/api/v1/puzzles/packs/{pack['pack_id']}/probe",
            json={
                "baseline_kind": "first",
                "seed": 7,
                "n_trials": 2,
            },
        )
    ).json()["data"]
    endpoint = f"{BASE}/puzzle-results/{pack['pack_id']}/{report['run_id']}"
    preview = await client.get(endpoint)
    assert preview.status_code == 200, preview.text
    reference = {
        "pack_id": pack["pack_id"],
        "run_id": report["run_id"],
        "expected_report_hash": preview.json()["data"]["result"]["report_hash"],
        "note": "Exploratory only",
    }
    draft = {
        "expected_revision": 0,
        "observations": "Observed choices",
        "interpretation": "",
        "limitations": "Selected position, not independent games",
        "evidence": [],
        "puzzle_evidence": [reference],
    }
    root = Path(test_settings.data_dir) / "puzzles" / pack["pack_id"]
    return root, endpoint, draft, preview.json()["data"]


async def test_publish_freezes_test_and_sources_without_execution(
    client: AsyncClient, citation, test_settings: Settings
):
    root, _, draft, preview = citation
    with patch(
        "app.services.puzzle_service.PuzzleService._decide_action_id",
        side_effect=AssertionError("No execution"),
    ):
        published = await client.post(f"{BASE}/conclusions", json=draft)
        assert published.status_code == 201, published.text
        data = published.json()["data"]
        record = data["record"]
        assert record["puzzle_evidence"][0]["note"] == "Exploratory only"
        assert record["puzzle_evidence"][0]["result"]["report"] == preview["result"]["report"]
        assert (
            record["puzzle_evidence"][0]["result"]["report_hash"]
            == preview["result"]["report_hash"]
        )
        assert record["puzzle_evidence"][0]["sources"] == preview["sources"]
        assert data["puzzle_evidence_status"][0]["record_status"] == "available"
        assert (await client.post(f"{BASE}/conclusions", json=draft)).status_code == 409
        report_id = record["id"]
        endpoint = f"/api/v1/experiments/conclusions/{report_id}/export"
        path = root / "runs" / f"{draft['puzzle_evidence'][0]['run_id']}.json"
        original = path.read_text(encoding="utf-8")
        modified = json.loads(original)
        modified["seed"] += 1
        path.write_text(json.dumps(modified), encoding="utf-8")
        changed = (await client.get(endpoint)).json()["data"]
        assert changed["record"] == record
        assert changed["puzzle_evidence_status"][0]["record_status"] == "changed"
        modified["metric_version"] = "unknown-version"
        path.write_text(json.dumps(modified), encoding="utf-8")
        assert (await client.get(endpoint)).json()["data"]["puzzle_evidence_status"][0][
            "record_status"
        ] == "unsupported"
        path.write_text('{"incomplete":', encoding="utf-8")
        assert (await client.get(endpoint)).json()["data"]["puzzle_evidence_status"][0][
            "record_status"
        ] == "invalid"
        path.unlink()
        async with connect_sqlite(test_settings.sqlite_path) as db:
            await db.execute("DELETE FROM decision_points WHERE id='source-d2'")
            await db.commit()
        missing = (await client.get(endpoint)).json()["data"]
        assert missing["record"] == record
        assert missing["puzzle_evidence_status"][0] == {
            "record_status": "missing",
            "source_status": None,
            "decisions": {"source-d2": "missing"},
        }
        assert missing["comparison"]["result"]["coverage"]["members"] == [
            {"seed": 42, "game_ids": {"source-run": "source-game"}}
        ]


@pytest.mark.parametrize(
    "change",
    [
        "hash",
        "pack",
        "summary",
        "legacy",
        "duplicate",
        "limit",
        "outside",
        "cutoff",
        "estimate",
        "identity",
    ],
)
async def test_invalid_citation_does_not_publish(
    client: AsyncClient, citation, test_settings: Settings, change: str
):
    root, endpoint, draft, _ = citation
    ref = draft["puzzle_evidence"][0]
    path = root / "runs" / f"{ref['run_id']}.json"
    if change in ("hash", "summary", "legacy"):
        report = json.loads(path.read_text(encoding="utf-8"))
        if change == "hash":
            report["seed"] += 1
        elif change == "summary":
            report["summary"]["repeat_consistency"] = 0.5
        else:
            report.pop("pack_snapshot")
            report.pop("pack_fingerprint")
        path.write_text(json.dumps(report), encoding="utf-8")
    elif change == "pack":
        manifest = root / "manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["extract"]["question"] = "New question"
        manifest.write_text(json.dumps(data), encoding="utf-8")
    elif change in ("duplicate", "limit"):
        draft["puzzle_evidence"] *= 2 if change == "duplicate" else 6
    else:
        async with connect_sqlite(test_settings.sqlite_path) as db:
            if change in ("outside", "cutoff"):
                snapshot = await ComparisonRepository(db).get("cmp")
                result = snapshot["result"]
                if change == "outside":
                    result["coverage"]["members"][0]["seed"] = 43
                else:
                    result["computed_at"] = "2000-01-01"
                await db.execute(
                    "UPDATE comparison_snapshots SET result=? WHERE id='cmp'", (json.dumps(result),)
                )
            elif change == "estimate":
                await db.execute(
                    "UPDATE decision_points SET evaluator_params='{}' WHERE id='source-d2'"
                )
            else:
                await db.execute(
                    "UPDATE decision_points SET player_id='unrelated' WHERE id='source-d2'"
                )
            await db.commit()
    response = await client.post(f"{BASE}/conclusions", json=draft)
    assert response.status_code == (409 if change == "hash" else 422), response.text
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []
    if change not in ("hash", "duplicate", "limit"):
        assert (await client.get(endpoint)).status_code == 422


async def test_puzzle_reference_survives_draft_reload(client: AsyncClient, citation):
    _, _, draft, _ = citation
    body = {"expected_revision": 0, "content": {"kind": "comparison", **draft}}
    saved = await client.put("/api/v1/drafts/comparison/cmp", json=body)
    assert saved.status_code == 200, saved.text
    restored = (await client.get("/api/v1/drafts/comparison/cmp")).json()["data"]
    assert restored["content"]["puzzle_evidence"] == draft["puzzle_evidence"]
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []


async def test_self_consistent_pack_edit_cannot_impersonate_source(client: AsyncClient, citation):
    root, endpoint, draft, _ = citation
    manifest, puzzles = load_pack(root)
    puzzles[0].observation["text"] = "An unrelated position"
    save_pack(root, manifest, puzzles)
    path = root / "runs" / f"{draft['puzzle_evidence'][0]['run_id']}.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["pack_fingerprint"] = pack_fingerprint(manifest, puzzles)
    report["pack_snapshot"] = pack_snapshot(manifest, puzzles)
    path.write_text(json.dumps(report), encoding="utf-8")
    preview = await client.get(endpoint)
    assert preview.status_code == 422, preview.text
    assert preview.json()["code"] == "RESEARCH_PUZZLE_SOURCE"
    assert (await client.post(f"{BASE}/conclusions", json=draft)).status_code == 422
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []


async def test_oversized_citation_does_not_publish(client: AsyncClient, citation):
    root, endpoint, draft, _ = citation
    ref = draft["puzzle_evidence"][0]
    path = root / "runs" / f"{ref['run_id']}.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["extra"] = "x" * (8 * 1024 * 1024)
    path.write_text(json.dumps(report), encoding="utf-8")
    preview = await client.get(endpoint)
    assert preview.status_code == 200, preview.text
    ref["expected_report_hash"] = preview.json()["data"]["result"]["report_hash"]
    response = await client.post(f"{BASE}/conclusions", json=draft)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "RESEARCH_PUZZLE_LIMIT"
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []
