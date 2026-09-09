"""Tests for rule-based policy memory notes and protocol accessor."""

from __future__ import annotations

from app.core.policy.memory_notes import build_rule_memory_notes
from app.core.task_protocol import build_protocol, protocol_memory


def test_build_rule_memory_notes_win() -> None:
    notes = build_rule_memory_notes(
        player_id="p1",
        winner_id="p1",
        decisions=[
            {"ev_loss": 0.1, "parse_fallback": False},
            {"ev_loss": 0.3, "parse_fallback": True},
        ],
    )
    assert "Last game: win" in notes
    assert "decisions=2" in notes
    assert "avg_ev_loss=0.200" in notes
    assert "parse_fallback=1" in notes


def test_protocol_memory_default_none() -> None:
    protocol = build_protocol(
        players=[{"id": "a"}],
        source_experiment_id=None,
        pair_deals=False,
        deal_seeds=[],
        frozen_at="t0",
        prompt_version="v3",
        collect_mode="free",
        protocol_fingerprint={"game_type": "doudizhu"},
    )
    assert protocol["solver"]["memory"] == "none"
    assert protocol_memory(protocol) == "none"


def test_protocol_memory_per_experiment() -> None:
    protocol = build_protocol(
        players=[{"id": "a"}],
        source_experiment_id=None,
        pair_deals=False,
        deal_seeds=[],
        frozen_at="t0",
        prompt_version="v3",
        collect_mode="free",
        protocol_fingerprint={"game_type": "doudizhu"},
        memory="per_experiment",
    )
    assert protocol_memory(protocol) == "per_experiment"
