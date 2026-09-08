"""Decision column values from Observation (Wave 4c / Wave 5)."""

from __future__ import annotations

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.engine.observation import Observation
from app.services.decision_snapshot import (
    baseline_suggestion_for_point,
    compact_tool_calls,
    game_phase_from_observation,
    hand_cards_from_observation,
    last_action_from_observation,
    opponent_hands_from_observation,
)


def _obs(**kwargs: object) -> Observation:
    base = dict(
        game_type="doudizhu",
        phase="playing",
        round=3,
        player_id="p1",
        to_act=True,
        private={},
        public={},
        text="",
    )
    base.update(kwargs)
    return Observation(**base)  # type: ignore[arg-type]


def test_hand_and_opponents_from_observation() -> None:
    observation = _obs(
        private={"hand_cards": ["SA", "H2"]},
        public={"hand_counts": {"p1": 2, "p2": 17, "p3": 16}},
    )
    assert hand_cards_from_observation(observation) == ["SA", "H2"]
    assert opponent_hands_from_observation(observation) == {"p2": 17, "p3": 16}


def test_last_action_maps_last_play() -> None:
    observation = _obs(
        public={
            "last_play": {
                "player_id": "p2",
                "action_type": "PAIR",
                "power": 5,
                "cards": ["H5", "S5"],
            }
        }
    )
    assert last_action_from_observation(observation) == {
        "player": "p2",
        "action_type": "PAIR",
        "cards": ["H5", "S5"],
    }


def test_last_action_none_without_last_play() -> None:
    assert last_action_from_observation(_obs()) is None


def test_game_phase_endgame_from_hand_counts() -> None:
    observation = _obs(
        phase="playing",
        public={"hand_counts": {"p1": 5, "p2": 12, "p3": 10}},
    )
    assert game_phase_from_observation(observation) == "endgame"


def test_game_phase_bidding() -> None:
    observation = _obs(phase="bidding", public={"hand_counts": {"p1": 17, "p2": 17, "p3": 17}})
    assert game_phase_from_observation(observation) == "bidding"


def test_compact_tool_calls_drops_analysis_keeps_keys() -> None:
    assert compact_tool_calls(None) is None
    assert compact_tool_calls({}) is None
    summary = compact_tool_calls(
        {
            "tool_analysis": "synthetic prose",
            "hand_analysis": {
                "strength_score": 0.6,
                "bomb_count": 1,
                "text": "一手炸弹",
            },
            "win_probability": {"probability": 0.4, "confidence": "low"},
        }
    )
    assert summary == [
        {
            "name": "analyze_hand",
            "keys": ["strength_score", "bomb_count"],
            "has_text": True,
        },
        {"name": "win_probability", "keys": ["probability", "confidence"]},
    ]


def test_baseline_suggestion_picks_cheapest_lead() -> None:
    """Leading with two singles: house heuristic sheds the lowest card."""
    point = {
        "player_id": "p1",
        "hand_cards": ["C3", "D5"],
        "opponent_hands": {"p2": 17, "p3": 16},
        "last_action": None,
        "game_phase": "playing",
        "legal_actions": [
            {
                "id": "PASS||",
                "label": "不出",
                "action_type": "PASS",
                "cards": [],
            },
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
    }
    action_id, label = baseline_suggestion_for_point(point, DoudizhuEngine())
    assert action_id == "SINGLE|C3|"
    assert label == "单张3"
