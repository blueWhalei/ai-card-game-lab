"""Unit tests for DPO preference-pair builder."""

from __future__ import annotations

import json

from app.core.training.preference import build_preference_pair


def _item(**overrides: object) -> dict:
    base: dict = {
        "id": "dp-1",
        "game_id": "g1",
        "round_number": 2,
        "player_id": "p1",
        "action_id": "PASS||",
        "thinking": "pass",
        "ev_loss": 0.2,
        "prompt_messages": [{"role": "user", "content": "menu"}],
        "evaluator_params": {
            "determinizations": 4,
            "best_action_id": "PLAY|3|",
            "action_values": {"PASS||": 0.1, "PLAY|3|": 0.9},
        },
    }
    base.update(overrides)
    return base


def test_build_pair_shape() -> None:
    record, skip = build_preference_pair(_item())
    assert skip is None
    assert record is not None
    assert record["messages"] == [{"role": "user", "content": "menu"}]
    assert json.loads(record["chosen"]) == {"action_id": "PLAY|3|"}
    assert json.loads(record["rejected"]) == {"action_id": "PASS||"}
    assert record["metadata"]["ev_loss"] == 0.2
    assert record["metadata"]["best_action_id"] == "PLAY|3|"


def test_include_thinking_only_on_rejected() -> None:
    record, skip = build_preference_pair(_item(), include_thinking=True)
    assert skip is None
    assert record is not None
    assert json.loads(record["chosen"]) == {"action_id": "PLAY|3|"}
    assert json.loads(record["rejected"])["thinking"] == "pass"


def test_skip_missing_best() -> None:
    record, skip = build_preference_pair(_item(evaluator_params={"determinizations": 4}))
    assert record is None
    assert skip == "missing_best"


def test_skip_tie() -> None:
    record, skip = build_preference_pair(
        _item(
            action_id="PLAY|3|",
            evaluator_params={"best_action_id": "PLAY|3|"},
            ev_loss=0.0,
        )
    )
    assert record is None
    assert skip == "tie"


def test_skip_gap() -> None:
    record, skip = build_preference_pair(_item(ev_loss=0.01), min_ev_gap=0.05)
    assert record is None
    assert skip == "gap"


def test_skip_missing_prompt() -> None:
    record, skip = build_preference_pair(_item(prompt_messages=None))
    assert record is None
    assert skip == "missing_prompt"
