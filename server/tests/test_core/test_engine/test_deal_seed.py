"""Deal seed reproducibility for Dou Dizhu."""

from __future__ import annotations

from app.core.engine.doudizhu.engine import DoudizhuEngine


def test_same_seed_same_hands_and_bid_order() -> None:
    engine = DoudizhuEngine()
    a = engine.initialize(["p1", "p2", "p3"], seed=42)
    b = engine.initialize(["p1", "p2", "p3"], seed=42)
    assert a.hands == b.hands
    assert a.landlord_cards == b.landlord_cards
    assert a.bid_order == b.bid_order
    assert a.current_player == b.current_player


def test_same_seed_different_ids_same_seat_hands() -> None:
    engine = DoudizhuEngine()
    a = engine.initialize(["a", "b", "c"], seed=99)
    b = engine.initialize(["x", "y", "z"], seed=99)
    assert a.hands["a"] == b.hands["x"]
    assert a.hands["b"] == b.hands["y"]
    assert a.hands["c"] == b.hands["z"]
    assert a.landlord_cards == b.landlord_cards
    seat_a = ["a", "b", "c"].index(a.bid_order[0])
    seat_b = ["x", "y", "z"].index(b.bid_order[0])
    assert seat_a == seat_b


def test_different_seeds_differ() -> None:
    engine = DoudizhuEngine()
    a = engine.initialize(["p1", "p2", "p3"], seed=1)
    b = engine.initialize(["p1", "p2", "p3"], seed=2)
    assert a.hands != b.hands or a.landlord_cards != b.landlord_cards
