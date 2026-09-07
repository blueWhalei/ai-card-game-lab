"""Core hand classification / comparison / legal-play smoke tests."""

from __future__ import annotations

from app.core.engine.doudizhu.cards import BLACK_JOKER, RED_JOKER, ActionType
from app.core.engine.doudizhu.hand_evaluator import can_beat, classify, get_legal_plays


def test_classify_rocket_bomb_chain_airplane() -> None:
    assert classify([BLACK_JOKER, RED_JOKER]) == (ActionType.ROCKET, 15)
    assert classify(["S3", "H3", "D3", "C3"]) == (ActionType.BOMB, 0)
    assert classify(["S3", "H4", "D5", "C6", "S7"])[0] == ActionType.CHAIN
    # Two consecutive triples = airplane
    plane = classify(["S3", "H3", "D3", "S4", "H4", "D4"])
    assert plane is not None
    assert plane[0] == ActionType.AIRPLANE


def test_classify_rejects_invalid() -> None:
    assert classify([]) is None
    assert classify(["S3", "H5"]) is None  # not a pair


def test_can_beat_rocket_and_bomb() -> None:
    assert can_beat(ActionType.SINGLE, 5, ActionType.ROCKET, 15) is True
    assert can_beat(ActionType.BOMB, 8, ActionType.ROCKET, 15) is True
    assert can_beat(ActionType.SINGLE, 5, ActionType.BOMB, 8) is True
    assert can_beat(ActionType.BOMB, 10, ActionType.BOMB, 8) is False
    assert can_beat(ActionType.ROCKET, 15, ActionType.BOMB, 12) is False


def test_can_beat_same_type_higher_power() -> None:
    assert can_beat(ActionType.SINGLE, 3, ActionType.SINGLE, 5) is True
    assert can_beat(ActionType.PAIR, 5, ActionType.PAIR, 4) is False
    assert can_beat(ActionType.SINGLE, 3, ActionType.PAIR, 5) is False


def test_get_legal_plays_includes_pass_when_following() -> None:
    hand = ["S5", "H5", "D7", "C8"]
    # Pair of 3s has primary power 0 (rank 3).
    last = (ActionType.PAIR, 0, ["S3", "H3"])
    plays = get_legal_plays(hand, last, "p1")
    types = {p.action_type for p in plays}
    assert ActionType.PASS in types
    assert ActionType.PAIR in types


def test_get_legal_plays_leading_has_no_pass() -> None:
    hand = ["S3", "H4"]
    plays = get_legal_plays(hand, None, "p1")
    assert all(p.action_type != ActionType.PASS for p in plays)
    assert any(p.action_type == ActionType.SINGLE for p in plays)
