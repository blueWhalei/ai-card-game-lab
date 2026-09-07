"""Puzzle pack IO, answer scoring, and spread-based selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.eval.puzzle import (
    PUZZLE_PACK_KIND,
    PUZZLE_SCHEMA_VERSION,
    Puzzle,
    PuzzlePackManifest,
    load_pack,
    save_pack,
    score_answer,
    select_by_spread,
)


def _puzzle_stub(*, game_id: str, spread: float, puzzle_id: str | None = None) -> Puzzle:
    return Puzzle(
        puzzle_id=puzzle_id or f"pz_{game_id}_{spread:.2f}",
        game_type="doudizhu",
        source={
            "experiment_id": "exp1",
            "game_id": game_id,
            "deal_seed": 42,
            "round_num": 1,
            "player_id": "p1",
        },
        observation={"phase": "playing"},
        legal_actions=[{"id": "a", "label": "A", "action": {"action_type": "pass", "cards": []}}],
        action_values={"a": 0.5, "b": 0.2},
        best_action_id="a",
        spread=spread,
        candidates_evaluated=2,
        legal_action_count=5,
        truncated=True,
        evaluator_params={"determinizations": 4},
    )


def _manifest_stub(*, pack_id: str = "pack_test") -> PuzzlePackManifest:
    return PuzzlePackManifest(
        pack_id=pack_id,
        created_at="2026-01-01T00:00:00+00:00",
        game_type="doudizhu",
        source_experiment_id="exp1",
        puzzle_count=1,
        extract={
            "min_spread": 0.15,
            "max_per_game": 2,
            "max_total": 3,
            "evaluator_params": {"determinizations": 4},
        },
        notes="test pack",
    )


def test_score_answer_hit_and_miss() -> None:
    values = {"a": 0.9, "b": 0.4, "c": 0.1}
    hit = score_answer("a", values, "a")
    assert hit.hit is True and hit.ev_loss == 0.0
    miss = score_answer("a", values, "b")
    assert miss.hit is False and miss.ev_loss == pytest.approx(0.5)
    outside = score_answer("a", values, "z")
    assert outside.hit is False and outside.ev_loss == pytest.approx(0.8)


def test_select_by_spread_caps() -> None:
    items = [
        _puzzle_stub(game_id="g1", spread=0.50),
        _puzzle_stub(game_id="g1", spread=0.40),
        _puzzle_stub(game_id="g1", spread=0.30),
        _puzzle_stub(game_id="g2", spread=0.35),
        _puzzle_stub(game_id="g2", spread=0.25),
        _puzzle_stub(game_id="g3", spread=0.10),
    ]
    picked = select_by_spread(items, min_spread=0.15, max_per_game=2, max_total=3)
    assert len(picked) == 3
    assert all(p.spread >= 0.15 for p in picked)
    g1_count = sum(1 for p in picked if p.source["game_id"] == "g1")
    assert g1_count <= 2
    spreads = [p.spread for p in picked]
    assert spreads == sorted(spreads, reverse=True)


def test_save_load_roundtrip(tmp_path: Path) -> None:
    manifest = _manifest_stub(pack_id="pack_roundtrip")
    puzzle = _puzzle_stub(game_id="g1", spread=0.31, puzzle_id="pz_one")
    save_pack(tmp_path / "pack1", manifest, [puzzle])
    m2, ps = load_pack(tmp_path / "pack1")
    assert m2.pack_id == manifest.pack_id and len(ps) == 1
    assert ps[0].puzzle_id == "pz_one"
    assert ps[0].spread == pytest.approx(0.31)
    assert m2.kind == PUZZLE_PACK_KIND
    assert m2.schema_version == PUZZLE_SCHEMA_VERSION


def test_load_pack_rejects_wrong_kind(tmp_path: Path) -> None:
    root = tmp_path / "bad_kind"
    root.mkdir()
    (root / "manifest.json").write_text(
        '{"kind": "other", "schema_version": 1, "pack_id": "x", '
        '"created_at": "2026-01-01T00:00:00+00:00", "game_type": "doudizhu", '
        '"source_experiment_id": "e", "puzzle_count": 0, "extract": {}, "notes": ""}',
        encoding="utf-8",
    )
    (root / "puzzles.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="kind"):
        load_pack(root)


def test_load_pack_rejects_wrong_schema_version(tmp_path: Path) -> None:
    root = tmp_path / "bad_version"
    root.mkdir()
    (root / "manifest.json").write_text(
        f'{{"kind": "{PUZZLE_PACK_KIND}", "schema_version": 99, "pack_id": "x", '
        '"created_at": "2026-01-01T00:00:00+00:00", "game_type": "doudizhu", '
        '"source_experiment_id": "e", "puzzle_count": 0, "extract": {}, "notes": ""}',
        encoding="utf-8",
    )
    (root / "puzzles.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_pack(root)
