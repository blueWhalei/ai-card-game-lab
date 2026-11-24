"""History reads preserve stored results, provenance and explicit failure states."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.eval.puzzle_results import save_result
from tests.test_services.test_puzzle_run import _tiny_pack


@pytest.fixture
async def history(client: AsyncClient, tmp_path: Path):
    manifest = _tiny_pack(tmp_path / "puzzles")
    root = tmp_path / "puzzles" / manifest.pack_id
    response = await client.post(
        f"/api/v1/puzzles/packs/{manifest.pack_id}/run", json={"baseline_kind": "first", "seed": 11}
    )
    assert response.status_code == 200, response.text
    return root, response.json()["data"]


async def test_saved_results_can_be_read_without_execution(client: AsyncClient, history) -> None:
    root, run = history
    response = await client.post(
        "/api/v1/puzzles/packs/pack-tiny/probe",
        json={"baseline_kind": "random", "seed": 3, "n_trials": 2, "kinds": ["shuffle_hand_cards"]},
    )
    assert response.status_code == 200
    probe = response.json()["data"]
    with patch(
        "app.services.puzzle_service.PuzzleService._decide_action_id",
        side_effect=AssertionError("Reading must not run policies"),
    ):
        listed = (await client.get("/api/v1/puzzles/packs/pack-tiny/results")).json()["data"]
        assert listed["total"] == 2
        assert listed["items"][0]["run_id"] == probe["run_id"]
        for record in (run, probe):
            result = await client.get(f"/api/v1/puzzles/packs/pack-tiny/results/{record['run_id']}")
            assert result.status_code == 200, result.text
            data = result.json()["data"]
            assert data["report"] == record
            assert data["source_status"] == "matched"
            assert len(data["report_hash"]) == 64
            assert data["report"]["pack_snapshot"]["manifest"]["source_experiment_id"] == "exp-x"
    assert len(list((root / "runs").glob("*.json"))) == 2


async def test_pack_changes_and_missing_files_do_not_rewrite_history(
    client: AsyncClient, history
) -> None:
    root, report = history
    endpoint = f"/api/v1/puzzles/packs/pack-tiny/results/{report['run_id']}"
    original = (root / "runs" / f"{report['run_id']}.json").read_bytes()
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["notes"] = "Changed after the test"
    (root / "manifest.json").write_text(json.dumps(manifest))
    result = (await client.get(endpoint)).json()["data"]
    assert result["source_status"] == "changed"
    assert result["report"] == report
    (root / "manifest.json").write_text("invalid json")
    assert (await client.get(endpoint)).json()["data"]["source_status"] == "unreadable"
    (root / "manifest.json").unlink()
    assert (await client.get(endpoint)).json()["data"]["source_status"] == "missing"
    assert (await client.get("/api/v1/puzzles/packs/pack-tiny/results")).json()["data"][
        "total"
    ] == 1
    assert (root / "runs" / f"{report['run_id']}.json").read_bytes() == original


async def test_prior_v2_records_are_not_assigned_current_sources(
    client: AsyncClient, history
) -> None:
    root, report = history
    report.pop("pack_snapshot")
    report.pop("pack_fingerprint")
    file = root / "runs" / f"{report['run_id']}.json"
    file.write_text(json.dumps(report))
    before = file.read_bytes()
    data = (await client.get(f"/api/v1/puzzles/packs/pack-tiny/results/{report['run_id']}")).json()[
        "data"
    ]
    assert data["source_status"] == "unrecorded"
    assert data["report"] == report
    assert file.read_bytes() == before


async def test_invalid_and_unsupported_files_are_visible(client: AsyncClient, history) -> None:
    root, report = history
    (root / "runs" / "run_00000000.json").write_text('{"incomplete":')
    other = {**report, "run_id": "run_11111111", "metric_version": "future-version"}
    (root / "runs" / "run_11111111.json").write_text(json.dumps(other))
    (root / "runs" / "unfinished.tmp").write_text("not published")
    listed = (await client.get("/api/v1/puzzles/packs/pack-tiny/results")).json()["data"]
    assert listed["total"] == 3
    status = {item["run_id"]: item["status"] for item in listed["items"]}
    assert status["run_00000000"] == "invalid"
    assert status["run_11111111"] == "unsupported"
    for identity in ("run_00000000", "run_11111111"):
        assert (
            await client.get(f"/api/v1/puzzles/packs/pack-tiny/results/{identity}")
        ).status_code == 422
    assert (
        await client.get("/api/v1/puzzles/packs/pack-tiny/results/run_22222222")
    ).status_code == 404


async def test_pagination_and_pack_identity(client: AsyncClient, history) -> None:
    root, report = history
    for index in range(22):
        item = {
            **report,
            "run_id": f"run_{index:08x}",
            "created_at": f"2020-01-01T00:00:{index:02d}+00:00",
        }
        save_result(root / "runs", item)
    one = (await client.get("/api/v1/puzzles/packs/pack-tiny/results")).json()["data"]
    two = (await client.get("/api/v1/puzzles/packs/pack-tiny/results?page=2")).json()["data"]
    assert one["total"] == 23 and len(one["items"]) == 20 and len(two["items"]) == 3
    assert one["items"][0]["run_id"] == report["run_id"]
    assert not {r["run_id"] for r in one["items"]} & {r["run_id"] for r in two["items"]}
    assert (await client.get("/api/v1/puzzles/packs/pack-tiny/results?page=0")).status_code == 422
    assert (await client.get("/api/v1/puzzles/packs/pack-tiny/results?page=3")).json()["data"][
        "items"
    ] == []
    assert (await client.get("/api/v1/puzzles/packs/another/results")).status_code == 404


@pytest.mark.parametrize(
    "change", ["owner", "denominator", "null", "nonfinite", "snapshot", "row", "summary", "source"]
)
async def test_inconsistent_records_are_rejected(client: AsyncClient, history, change: str) -> None:
    root, original = history
    report = copy.deepcopy(original)
    if change == "owner":
        report["pack_id"] = "foreign"
    elif change == "denominator":
        report["summary"]["evaluated_n"] += 1
    elif change == "null":
        report["summary"]["accuracy"] = None
    elif change == "nonfinite":
        report["summary"]["accuracy"] = float("nan")
    elif change == "snapshot":
        report["pack_snapshot"]["manifest"]["pack_id"] = "foreign"
    elif change == "summary":
        report["summary"]["accuracy"] = 1 - report["summary"]["accuracy"]
    elif change == "source":
        report["pack_snapshot"]["puzzles"][0]["candidates_evaluated"] = -1
    else:
        report["puzzles"][0]["ev_loss"] = None
    (root / "runs" / f"{report['run_id']}.json").write_text(json.dumps(report))
    assert (
        await client.get(f"/api/v1/puzzles/packs/pack-tiny/results/{report['run_id']}")
    ).status_code == 422


@pytest.mark.parametrize("change", ["coverage", "agreement", "action"])
async def test_corrupt_probe_records_are_rejected(
    client: AsyncClient, history, change: str
) -> None:
    root, _ = history
    report = (
        await client.post(
            "/api/v1/puzzles/packs/pack-tiny/probe",
            json={"baseline_kind": "first", "seed": 0, "n_trials": 2},
        )
    ).json()["data"]
    if change == "coverage":
        report["summary"]["pert_evaluated_n"] = 0
        report["summary"]["pert_unevaluated_n"] = report["summary"]["comparisons_n"]
        report["summary"]["pert_accuracy"] = None
        report["summary"]["pert_mean_ev_loss"] = None
    elif change == "agreement":
        report["summary"]["repeat_consistency"] = 1 - report["summary"]["repeat_consistency"]
    else:
        report["puzzles"][0]["trials"][0]["control_action_id"] = "unrelated"
    (root / "runs" / f"{report['run_id']}.json").write_text(json.dumps(report))
    assert (
        await client.get(f"/api/v1/puzzles/packs/pack-tiny/results/{report['run_id']}")
    ).status_code == 422


async def test_directory_restrictions_and_atomic_no_overwrite(client: AsyncClient, history) -> None:
    root, report = history
    file = root / "runs" / f"{report['run_id']}.json"
    original = file.read_bytes()
    with pytest.raises(FileExistsError):
        save_result(root / "runs", {**report, "seed": 999})
    assert file.read_bytes() == original
    assert not list((root / "runs").glob("*.tmp"))
    for path in ("..%5Coutside/results", "pack-tiny/results/..%5Coutside", "C%3Atest/results"):
        result = await client.get(f"/api/v1/puzzles/packs/{path}")
        assert result.status_code == 422, result.text
