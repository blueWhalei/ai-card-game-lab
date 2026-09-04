"""Scenario bucket classification for experiment contrast."""

from __future__ import annotations

from app.core.stats.scenarios import (
    classify_game_phase,
    classify_scenario,
    fill_scenario_scores,
    scenario_rate_diffs,
)


def test_classify_game_phase_endgame_when_any_hand_short() -> None:
    assert classify_game_phase(engine_phase="bidding", hand_sizes=[17, 17, 17]) == "bidding"
    assert classify_game_phase(engine_phase="playing", hand_sizes=[17, 17, 16]) == "playing"
    assert classify_game_phase(engine_phase="playing", hand_sizes=[20, 8, 17]) == "endgame"
    assert classify_game_phase(engine_phase="playing", hand_sizes=[0, 12, 12]) == "playing"


def test_classify_scenario_priority() -> None:
    assert classify_scenario(game_phase="playing", hand_size=12, action_type="BID") == "bidding"
    assert classify_scenario(game_phase="playing", hand_size=3, action_type="BOMB") == "bomb"
    assert classify_scenario(game_phase="playing", hand_size=5, action_type="SINGLE") == "endgame"
    assert classify_scenario(game_phase="playing", hand_size=12, action_type="PASS") == "playing"
    assert classify_scenario(game_phase="endgame", hand_size=12, action_type="PASS") == "endgame"


def test_fill_scenario_scores_always_four_buckets() -> None:
    filled = fill_scenario_scores(
        {
            "bidding": {"n": 10, "train_usable_n": 8, "parser_n": 10, "parser_ok": 9},
            "early": {"n": 2, "train_usable_n": 2, "parser_n": 0, "parser_ok": 0},
        }
    )
    assert set(filled) == {"bidding", "playing", "endgame", "bomb"}
    assert filled["bidding"]["train_usable_rate"] == 0.8
    assert filled["bidding"]["parser_success_rate"] == 0.9
    assert filled["playing"]["n"] == 2
    assert filled["endgame"]["n"] == 0
    assert filled["bomb"]["n"] == 0


def test_scenario_rate_diffs_null_when_missing_n() -> None:
    this = fill_scenario_scores(
        {"bidding": {"n": 10, "train_usable_n": 8, "parser_n": 10, "parser_ok": 8}}
    )
    peer = fill_scenario_scores(
        {"bidding": {"n": 10, "train_usable_n": 5, "parser_n": 10, "parser_ok": 10}}
    )
    diffs = scenario_rate_diffs(this, peer)
    assert diffs["bidding"]["train_usable_rate_diff"] == 0.3
    assert diffs["bidding"]["parser_success_rate_diff"] == -0.2
    assert diffs["endgame"]["train_usable_rate_diff"] is None
    assert diffs["bomb"]["parser_success_rate_diff"] is None
