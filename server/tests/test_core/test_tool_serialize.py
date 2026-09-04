"""Serialize tool results for traces / WebSocket explain payload."""

from __future__ import annotations

from app.core.ai.tools.hand_analyzer import HandAnalysis
from app.core.ai.tools.serialize import (
    actions_as_dicts,
    explain_from_tools,
)
from app.core.ai.tools.win_probability import WinProbabilityResult
from app.core.engine.base import GameAction


def test_explain_from_tools_compacts_dataclasses() -> None:
    payload = explain_from_tools(
        {
            "win_probability": WinProbabilityResult(
                probability=0.62,
                confidence="中",
                factors=["有炸弹"],
                reasoning="局势均衡",
            ),
            "hand_analysis": HandAnalysis(
                total_cards=12,
                bomb_count=1,
                rocket=False,
                high_cards=["RJ"],
                potential_chains=0,
                strength_score=0.7,
                recommendations=["出炸弹"],
            ),
            "tool_analysis": "ignored",
        }
    )
    assert payload["win_probability"]["probability"] == 0.62
    assert payload["win_probability"]["confidence"] == "中"
    assert payload["hand_analysis"] == {
        "bomb_count": 1,
        "rocket": False,
        "strength_score": 0.7,
    }
    assert "tool_analysis" not in payload


def test_explain_from_tools_empty() -> None:
    assert explain_from_tools(None) == {}
    assert explain_from_tools({}) == {}


def test_actions_as_dicts() -> None:
    actions = [
        GameAction(player_id="p1", action_type="PASS", cards=[]),
        GameAction(player_id="p1", action_type="PAIR", cards=["S3", "H3"]),
    ]
    assert actions_as_dicts(actions) == [
        {"action_type": "PASS", "cards": []},
        {"action_type": "PAIR", "cards": ["S3", "H3"]},
    ]
