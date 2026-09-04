"""Post-game highlight picking from stored decision points."""

from __future__ import annotations

from typing import Any

from app.core.stats.highlights import pick_game_highlights


def _pt(
    decision_id: str,
    *,
    round_number: int,
    player_id: str = "p1",
    action_type: str = "SINGLE",
    cards: list[str] | None = None,
    game_phase: str = "playing",
    hand_n: int = 12,
    legal_n: int = 3,
    parser_ok: bool | None = True,
) -> dict[str, Any]:
    return {
        "id": decision_id,
        "round_number": round_number,
        "player_id": player_id,
        "game_phase": game_phase,
        "hand_cards": ["H3"] * hand_n,
        "legal_actions": [{"action_type": "PASS", "cards": []}] * legal_n,
        "chosen_action": {"action_type": action_type, "cards": cards or ["H3"]},
        "parser_ok": parser_ok,
    }


def test_empty_points_returns_empty() -> None:
    assert pick_game_highlights([]) == []
    assert pick_game_highlights([{"round_number": 1}]) == []


def test_last_play_is_winner_latest_round() -> None:
    points = [
        _pt("a", round_number=1, player_id="p1"),
        _pt("b", round_number=2, player_id="p2"),
        _pt("c", round_number=3, player_id="p1"),
    ]
    rows = pick_game_highlights(points, winner_id="p2")
    last = next(r for r in rows if r["reason"] == "last_play")
    assert last["decision_id"] == "b"
    assert last["round_number"] == 2


def test_no_winner_uses_global_last_round() -> None:
    points = [
        _pt("a", round_number=1),
        _pt("b", round_number=4),
        _pt("c", round_number=2),
    ]
    rows = pick_game_highlights(points, winner_id=None)
    last = next(r for r in rows if r["reason"] == "last_play")
    assert last["decision_id"] == "b"


def test_bomb_and_fallback_and_endgame_and_branch() -> None:
    points = [
        _pt("last", round_number=20, player_id="p1"),
        _pt("bomb1", round_number=5, action_type="BOMB", cards=["H3"] * 4),
        _pt("rocket", round_number=8, action_type="ROCKET", cards=["RJ", "BJ"]),
        _pt("fb", round_number=6, parser_ok=False),
        _pt("end", round_number=15, hand_n=4),
        _pt("br", round_number=9, legal_n=10),
    ]
    rows = pick_game_highlights(points, winner_id="p1")
    reasons = {r["decision_id"]: r["reason"] for r in rows}
    assert reasons["last"] == "last_play"
    assert reasons["bomb1"] == "bomb"
    assert reasons["rocket"] == "bomb"
    assert reasons["fb"] == "fallback"
    assert reasons["end"] == "endgame"
    # Cap is 5: last + 2 bombs + fallback + endgame (branch dropped)
    assert "br" not in reasons
    assert [r["round_number"] for r in rows] == sorted(r["round_number"] for r in rows)


def test_bomb_diversity_cap() -> None:
    points = [_pt(f"b{i}", round_number=i, action_type="BOMB") for i in range(1, 6)]
    rows = pick_game_highlights(points, winner_id="p1")
    bombs = [r for r in rows if r["reason"] == "bomb"]
    lasts = [r for r in rows if r["reason"] == "last_play"]
    assert len(lasts) == 1
    assert lasts[0]["decision_id"] == "b5"
    assert len(bombs) <= 2


def test_fill_to_three_from_ordinary_plays() -> None:
    points = [_pt(f"p{i}", round_number=i, legal_n=2, hand_n=12) for i in range(1, 6)]
    rows = pick_game_highlights(points, winner_id="p1")
    assert len(rows) >= 3
    assert any(r["reason"] == "last_play" for r in rows)
    assert any(r["reason"] == "play" for r in rows)


def test_single_point_game() -> None:
    rows = pick_game_highlights([_pt("only", round_number=1)], winner_id="p1")
    assert len(rows) == 1
    assert rows[0]["reason"] == "last_play"
    assert rows[0]["action_type"] == "SINGLE"
    assert rows[0]["cards"] == ["H3"]


def test_respects_limit() -> None:
    points = [
        _pt("last", round_number=10),
        _pt("b1", round_number=1, action_type="BOMB"),
        _pt("b2", round_number=2, action_type="ROCKET"),
        _pt("f1", round_number=3, parser_ok=False),
        _pt("e1", round_number=4, hand_n=3),
    ]
    rows = pick_game_highlights(points, winner_id="p1", limit=3)
    assert len(rows) == 3
