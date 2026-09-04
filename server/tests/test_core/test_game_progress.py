from app.core.stats.game_progress import build_game_progress, resolve_progress_phase


def test_resolve_progress_phase() -> None:
    assert resolve_progress_phase(None) == "queued"
    assert resolve_progress_phase("") == "queued"
    assert resolve_progress_phase("bidding") == "bidding"
    assert resolve_progress_phase("endgame") == "endgame"
    assert resolve_progress_phase("playing") == "playing"
    assert resolve_progress_phase("early") == "playing"


def test_build_game_progress_queued_without_moves() -> None:
    assert build_game_progress() == {"phase": "queued", "round": None, "player_id": None}


def test_build_game_progress_playing() -> None:
    assert build_game_progress(
        game_phase="playing",
        round_number=12,
        player_id="aggressive_tiger",
    ) == {
        "phase": "playing",
        "round": 12,
        "player_id": "aggressive_tiger",
    }
