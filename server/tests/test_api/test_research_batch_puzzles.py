"""Batch citations require selection provenance and every source, without new simulation."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.core.eval.puzzle import load_pack, save_pack
from app.core.eval.puzzle_results import digest, pack_fingerprint, pack_snapshot
from app.database import connect_sqlite
from app.repositories.comparison_repo import ComparisonRepository
from tests.test_api.test_decision_puzzles import seed_source

BASE = "/api/v1/experiments/comparisons/batch-cmp"


@pytest.fixture
async def batch(client: AsyncClient, test_settings: Settings):
    await seed_source(test_settings.sqlite_path)
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await ComparisonRepository(db).create(
            "batch-cmp",
            "Synthetic batch citation",
            datetime.now(UTC).isoformat(),
            {
                "computed_at": datetime.now(UTC).isoformat(),
                "experiments": [{"id": "source-run", "game_ids": ["source-game"]}],
                "coverage": {"members": [{"seed": 42, "game_ids": {"source-run": "source-game"}}]},
            },
        )

    # These fresh synthetic values intentionally differ from the source's stored 0.7/0.2.
    def estimates(_self, observation, legal):
        return {entry.id: (0.9 if i == 0 else 0.1) for i, entry in enumerate(legal[:2])}

    with patch("app.core.eval.rollout.RolloutEvaluator.action_values", estimates):
        response = await client.post(
            "/api/v1/puzzles/extract",
            json={
                "experiment_id": "source-run",
                "min_spread": 0.5,
                "max_per_game": 3,
                "max_total": 3,
            },
        )
    assert response.status_code == 200, response.text
    pack = response.json()["data"]
    assert pack["puzzle_count"] == 3
    assert (
        len(pack["extract"]["selection"]["candidates"]) == 4
    )  # the last decision has one legal action
    assert pack["extract"]["selection"]["selected_game_ids"] == ["source-game"]
    assert all("decision_hash" in check for check in pack["extract"]["source_checks"].values())
    report = (
        await client.post(
            f"/api/v1/puzzles/packs/{pack['pack_id']}/run",
            json={"baseline_kind": "first", "seed": 7},
        )
    ).json()["data"]
    endpoint = f"{BASE}/puzzle-results/{pack['pack_id']}/{report['run_id']}"
    response = await client.get(endpoint)
    assert response.status_code == 200, response.text
    preview = response.json()["data"]
    draft = {
        "expected_revision": 0,
        "observations": "Selected diagnostic positions",
        "interpretation": "",
        "limitations": "Synthetic estimates, selected positions are not independent games",
        "evidence": [],
        "puzzle_evidence": [
            {
                "pack_id": pack["pack_id"],
                "run_id": report["run_id"],
                "expected_report_hash": preview["result"]["report_hash"],
                "note": "Selection bias",
            }
        ],
    }
    root = Path(test_settings.data_dir) / "puzzles" / pack["pack_id"]
    return root, endpoint, draft, preview


async def test_batch_publication_freezes_every_source_and_keeps_original_estimates(
    client: AsyncClient, batch, test_settings: Settings
):
    root, _, draft, preview = batch
    packs = (await client.get(f"{BASE}/puzzle-packs")).json()["data"]
    assert [p["pack_id"] for p in packs] == [root.name]
    with (
        patch(
            "app.core.eval.rollout.RolloutEvaluator.action_values",
            side_effect=AssertionError("No re-evaluation"),
        ),
        patch(
            "app.services.puzzle_service.PuzzleService._decide_action_id",
            side_effect=AssertionError("No test execution"),
        ),
    ):
        response = await client.post(f"{BASE}/conclusions", json=draft)
        assert response.status_code == 201, response.text
        published = response.json()["data"]
        record = published["record"]
        sources = record["puzzle_evidence"][0]["sources"]
        assert [s["decision"]["id"] for s in sources] == ["source-d0", "source-d1", "source-d2"]
        assert (
            sources[0]["decision"]["evaluator_params"]["action_values"]
            == preview["sources"][0]["decision"]["evaluator_params"]["action_values"]
        )
        assert max(sources[0]["decision"]["evaluator_params"]["action_values"].values()) == 0.7
        assert (
            load_pack(root)[1][0].action_values
            != sources[0]["decision"]["evaluator_params"]["action_values"]
        )
        assert set(published["puzzle_evidence_status"][0]["decisions"]) == {
            "source-d0",
            "source-d1",
            "source-d2",
        }
        async with connect_sqlite(test_settings.sqlite_path) as db:
            await db.execute("DELETE FROM decision_points WHERE id='source-d1'")
            await db.commit()
        (root / "runs" / f"{draft['puzzle_evidence'][0]['run_id']}.json").unlink()
        data = (await client.get(f"/api/v1/experiments/conclusions/{record['id']}/export")).json()[
            "data"
        ]
        assert data["record"] == record
        assert data["puzzle_evidence_status"][0]["record_status"] == "missing"
        assert data["puzzle_evidence_status"][0]["decisions"]["source-d1"] == "missing"
        assert len(data["comparison"]["result"]["coverage"]["members"]) == 1


@pytest.mark.parametrize(
    "change",
    [
        "legacy",
        "ledger",
        "limit",
        "threshold",
        "duplicate",
        "observation",
        "estimate",
        "source",
        "last_source",
        "outside",
        "order",
        "parameters",
        "malformed_check",
    ],
)
async def test_bad_batch_refuses_the_whole_citation(
    client: AsyncClient, batch, test_settings: Settings, change: str
):
    root, endpoint, draft, _ = batch
    manifest, positions = load_pack(root)
    selection = manifest.extract
    if change in ("source", "last_source", "outside"):
        async with connect_sqlite(test_settings.sqlite_path) as db:
            if change == "outside":
                await db.execute("UPDATE games SET metadata='{}' WHERE id='source-game'")
            else:
                target = "source-d2" if change == "last_source" else "source-d0"
                await db.execute(
                    "UPDATE decision_points SET annotation='doubt' WHERE id=?", (target,)
                )
            await db.commit()
    else:
        if change == "legacy":
            selection.pop("source_checks")
        elif change == "malformed_check":
            selection["source_checks"][positions[1].puzzle_id] = None
        elif change == "ledger":
            selection["selection"]["candidates"].pop(0)
        elif change == "limit":
            selection["max_per_game"] = 1
        elif change == "threshold":
            selection["min_spread"] = 0.95
        elif change == "order":
            selection["selection"]["candidates"].reverse()
        elif change == "parameters":
            positions[2].evaluator_params = {**positions[2].evaluator_params, "seed": 99}
            selection["source_checks"][positions[2].puzzle_id]["puzzle_hash"] = digest(
                positions[2].to_dict()
            )
        elif change == "duplicate":
            positions[1].source["decision_point_id"] = positions[0].source["decision_point_id"]
        elif change == "observation":
            positions[2].observation["text"] = "Unrelated position"
            selection["source_checks"][positions[2].puzzle_id]["puzzle_hash"] = digest(
                positions[2].to_dict()
            )
        elif change == "estimate":
            positions[2].action_values[positions[2].best_action_id] = float("inf")
        save_pack(root, manifest, positions)
        if change != "estimate":
            path = root / "runs" / f"{draft['puzzle_evidence'][0]['run_id']}.json"
            report = json.loads(path.read_text(encoding="utf-8"))
            report["pack_snapshot"] = pack_snapshot(manifest, positions)
            report["pack_fingerprint"] = pack_fingerprint(manifest, positions)
            path.write_text(json.dumps(report), encoding="utf-8")
    rejected = await client.get(endpoint)
    assert rejected.status_code == 422, rejected.text
    assert (await client.post(f"{BASE}/conclusions", json=draft)).status_code == 422
    assert (await client.get(f"{BASE}/conclusions")).json()["data"] == []
