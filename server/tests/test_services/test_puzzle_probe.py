"""PuzzleService.probe: consistency under presentation shuffles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.engine.registry import GameEngineRegistry
from app.core.eval.puzzle import Puzzle, PuzzlePackManifest, save_pack
from app.services.puzzle_service import PuzzleService


def _order_sensitive_pack(root: Path) -> PuzzlePackManifest:
    """Best action is second in the menu so rule/first is order-sensitive."""
    manifest = PuzzlePackManifest(
        pack_id="pack-probe",
        created_at="2026-09-08T00:00:00+00:00",
        game_type="doudizhu",
        source_experiment_id="exp-x",
        puzzle_count=1,
        extract={},
    )
    puzzle = Puzzle(
        puzzle_id="pz_order",
        game_type="doudizhu",
        source={"game_id": "g1", "player_id": "p1"},
        observation={
            "game_type": "doudizhu",
            "phase": "playing",
            "round": 1,
            "player_id": "p1",
            "to_act": True,
            "private": {"hand_cards": ["3", "4", "5"]},
            "public": {},
            "text": "",
        },
        legal_actions=[
            {
                "id": "PASS||",
                "label": "PASS",
                "action": {"action_type": "PASS", "cards": [], "target": None},
            },
            {
                "id": "PLAY|3|",
                "label": "PLAY",
                "action": {"action_type": "PLAY", "cards": ["3"], "target": None},
            },
        ],
        action_values={"PASS||": 0.2, "PLAY|3|": 0.9},
        best_action_id="PLAY|3|",
        spread=0.7,
        candidates_evaluated=2,
        legal_action_count=2,
        truncated=False,
    )
    save_pack(root / manifest.pack_id, manifest, [puzzle])
    return manifest


@pytest.fixture
def probe_service(tmp_path: Path) -> PuzzleService:
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    return PuzzleService(
        sqlite_path=str(tmp_path / "unused.db"),
        puzzle_dir=str(tmp_path / "puzzles"),
        engine_registry=registry,
    )


@pytest.mark.asyncio
async def test_probe_rule_consistency_below_one(
    probe_service: PuzzleService, tmp_path: Path
) -> None:
    puzzle_dir = tmp_path / "puzzles"
    manifest = _order_sensitive_pack(puzzle_dir)

    report = await probe_service.probe(
        manifest.pack_id,
        baseline_kind="rule",
        seed=1,
        n_trials=8,
        kinds=["shuffle_legal_actions"],
    )
    summary = report["summary"]
    assert summary["n"] == 1
    assert summary["n_trials"] == 8
    assert summary["kinds"] == ["shuffle_legal_actions"]
    # FirstAction always picks menu[0]; shuffling often moves PASS off the front.
    assert summary["consistency"] < 1.0
    assert "base_accuracy" in summary and "pert_accuracy" in summary
    run_path = puzzle_dir / manifest.pack_id / "runs" / f"{report['run_id']}.json"
    assert run_path.is_file()
    loaded = json.loads(run_path.read_text(encoding="utf-8"))
    assert loaded["summary"]["consistency"] == summary["consistency"]


@pytest.mark.asyncio
async def test_probe_reproducible_with_same_seed(
    probe_service: PuzzleService, tmp_path: Path
) -> None:
    puzzle_dir = tmp_path / "puzzles"
    manifest = _order_sensitive_pack(puzzle_dir)
    a = await probe_service.probe(manifest.pack_id, baseline_kind="rule", seed=42, n_trials=5)
    b = await probe_service.probe(manifest.pack_id, baseline_kind="rule", seed=42, n_trials=5)
    assert a["summary"] == b["summary"]
    assert a["puzzles"][0]["trials"] == b["puzzles"][0]["trials"]
