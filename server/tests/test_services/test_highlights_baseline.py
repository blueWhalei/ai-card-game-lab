"""Highlight rows gain a heuristic baseline on read (Wave 5)."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.decision_service import DecisionService

_POINT: dict[str, Any] = {
    "id": "dp_lead",
    "round_number": 3,
    "player_id": "p1",
    "game_phase": "playing",
    "hand_cards": ["C3", "D5"],
    "opponent_hands": {"p2": 17, "p3": 16},
    "last_action": None,
    "legal_actions": [
        {"id": "PASS||", "label": "不出", "action_type": "PASS", "cards": []},
        {
            "id": "SINGLE|C3|",
            "label": "单张3",
            "action_type": "SINGLE",
            "cards": ["C3"],
        },
        {
            "id": "SINGLE|D5|",
            "label": "单张5",
            "action_type": "SINGLE",
            "cards": ["D5"],
        },
    ],
    "chosen_action": {"action_type": "SINGLE", "cards": ["D5"]},
    "action_id": "SINGLE|D5|",
    "parser_ok": True,
    "ev_loss": 0.2,
    "evaluator_params": {"best_action_id": "SINGLE|C3|"},
}


@pytest.mark.asyncio
async def test_highlights_for_game_adds_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = DecisionService(":memory:")

    async def fake_list(**_kwargs: object) -> tuple[list[dict[str, Any]], int]:
        return [_POINT], 1

    async def fake_game_type(_game_id: str) -> str:
        return "doudizhu"

    monkeypatch.setattr(svc, "list_decision_points", fake_list)
    monkeypatch.setattr(svc, "_game_type_for", fake_game_type)

    rows = await svc.highlights_for_game("g1", winner_id="p1")
    assert rows
    hit = next(r for r in rows if r["decision_id"] == "dp_lead")
    assert hit["baseline_action_id"] == "SINGLE|C3|"
    assert hit["baseline_label"] == "单张3"


@pytest.mark.asyncio
async def test_commentary_for_game_adds_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = DecisionService(":memory:")

    async def fake_list(**_kwargs: object) -> tuple[list[dict[str, Any]], int]:
        return [_POINT], 1

    async def fake_game_type(_game_id: str) -> str:
        return "doudizhu"

    monkeypatch.setattr(svc, "list_decision_points", fake_list)
    monkeypatch.setattr(svc, "_game_type_for", fake_game_type)

    rows = await svc.commentary_for_game("g1")
    assert len(rows) == 1
    hit = rows[0]
    assert hit["decision_id"] == "dp_lead"
    assert hit["action_id"] == "SINGLE|D5|"
    assert hit["best_action_id"] == "SINGLE|C3|"
    assert hit["baseline_action_id"] == "SINGLE|C3|"
    assert hit["baseline_label"] == "单张3"
    assert "reason" not in hit
