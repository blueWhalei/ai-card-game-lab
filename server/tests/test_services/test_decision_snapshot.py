"""Decision column values from Observation (Wave 4c)."""

from __future__ import annotations

from app.core.engine.observation import Observation
from app.services.decision_snapshot import (
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
