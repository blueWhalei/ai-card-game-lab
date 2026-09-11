"""PuzzleService.run: score baselines against a frozen pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.engine.registry import GameEngineRegistry
from app.core.eval.puzzle import Puzzle, PuzzlePackManifest, save_pack
from app.services.puzzle_service import PuzzleService


def _tiny_pack(root: Path) -> PuzzlePackManifest:
    manifest = PuzzlePackManifest(
        pack_id="pack-tiny",
        created_at="2026-09-08T00:00:00+00:00",
        game_type="doudizhu",
        source_experiment_id="exp-x",
        puzzle_count=2,
        extract={"min_spread": 0.0, "max_per_game": 3, "max_total": 10},
    )
    puzzles = [
        Puzzle(
            puzzle_id="pz_a",
            game_type="doudizhu",
            source={"game_id": "g1", "round_num": 1, "player_id": "p1"},
            observation={
                "game_type": "doudizhu",
                "phase": "playing",
                "round": 1,
                "player_id": "p1",
                "to_act": True,
                "private": {},
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
                    "label": "PLAY 3",
                    "action": {"action_type": "PLAY", "cards": ["3"], "target": None},
                },
            ],
            action_values={"PASS||": 0.2, "PLAY|3|": 0.8},
            best_action_id="PLAY|3|",
            spread=0.6,
            candidates_evaluated=2,
            legal_action_count=2,
            truncated=False,
        ),
        Puzzle(
            puzzle_id="pz_b",
            game_type="doudizhu",
            source={"game_id": "g1", "round_num": 2, "player_id": "p1"},
            observation={
                "game_type": "doudizhu",
                "phase": "playing",
                "round": 2,
                "player_id": "p1",
                "to_act": True,
                "private": {},
                "public": {},
                "text": "",
            },
            legal_actions=[
                {
                    "id": "a",
                    "label": "a",
                    "action": {"action_type": "PASS", "cards": [], "target": None},
                },
                {
                    "id": "b",
                    "label": "b",
                    "action": {"action_type": "PLAY", "cards": ["4"], "target": None},
                },
            ],
            action_values={"a": 0.1, "b": 0.9},
            best_action_id="b",
            spread=0.8,
            candidates_evaluated=2,
            legal_action_count=5,
            truncated=True,
        ),
    ]
    save_pack(root / manifest.pack_id, manifest, puzzles)
    return manifest


@pytest.fixture
def run_service(tmp_path: Path) -> PuzzleService:
    registry = GameEngineRegistry()
    registry.register(DoudizhuEngine())
    return PuzzleService(
        sqlite_path=str(tmp_path / "unused.db"),
        puzzle_dir=str(tmp_path / "puzzles"),
        engine_registry=registry,
    )


@pytest.mark.asyncio
async def test_run_heuristic_writes_report(run_service: PuzzleService, tmp_path: Path) -> None:
    puzzle_dir = tmp_path / "puzzles"
    manifest = _tiny_pack(puzzle_dir)

    report = await run_service.run(manifest.pack_id, baseline_kind="first", seed=1)

    summary = report["summary"]
    assert summary["n"] == 2
    assert "accuracy" in summary
    assert "mean_ev_loss" in summary
    assert summary["truncated_n"] == 1
    assert report["baseline_kind"] == "first"
    # FirstActionPolicy always picks the first legal id → miss both bests.
    assert summary["accuracy"] == 0.0
    run_path = puzzle_dir / manifest.pack_id / "runs" / f"{report['run_id']}.json"
    assert run_path.is_file()
    loaded = json.loads(run_path.read_text(encoding="utf-8"))
    assert loaded["summary"]["n"] == 2


@pytest.mark.asyncio
async def test_run_empty_pack(run_service: PuzzleService, tmp_path: Path) -> None:
    puzzle_dir = tmp_path / "puzzles"
    manifest = PuzzlePackManifest(
        pack_id="pack-empty",
        created_at="2026-09-08T00:00:00+00:00",
        game_type="doudizhu",
        source_experiment_id="exp-x",
        puzzle_count=0,
        extract={},
    )
    save_pack(puzzle_dir / manifest.pack_id, manifest, [])

    report = await run_service.run(manifest.pack_id, baseline_kind="random")
    assert report["summary"] == {
        "n": 0,
        "accuracy": 0.0,
        "mean_ev_loss": 0.0,
        "truncated_n": 0,
    }


def test_list_packs(run_service: PuzzleService, tmp_path: Path) -> None:
    puzzle_dir = tmp_path / "puzzles"
    _tiny_pack(puzzle_dir)
    packs = run_service.list_packs()
    assert len(packs) == 1
    assert packs[0].pack_id == "pack-tiny"
