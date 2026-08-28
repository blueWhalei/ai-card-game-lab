"""ObserverSnapshot shape for Dou Dizhu get_public_info."""

from __future__ import annotations

from app.core.engine.doudizhu.engine import DoudizhuEngine


def test_get_public_info_observer_snapshot_shape() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["p1", "p2", "p3"], seed=42)
    info = engine.get_public_info(state, "observer", is_observer=True)

    assert info["game_type"] == "doudizhu"
    assert "phase" in info
    assert "round" in info
    assert "current_player_id" in info
    assert isinstance(info["players"], list)
    assert len(info["players"]) == 3

    for player in info["players"]:
        assert "id" in player
        assert "hand_count" in player
        assert "is_active" in player
        assert "hand_cards" in player

    assert "table" in info
    assert "slots" in info["table"]
    assert "extras" in info
    assert "landlord_cards" not in info
    assert "hands" not in info
