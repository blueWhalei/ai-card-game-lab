"""Validation must not see another run of a training deal."""

import pytest

from app.core.training.data_split import validation_groups


def test_repeated_deals_stay_together_independent_of_input_order() -> None:
    games = {
        gid: {"game_type": "doudizhu", "metadata": {"deal_seed": seed}}
        for gid, seed in [("a1", 1), ("b1", 1), ("a2", 2), ("b2", 2)]
    }
    selected, meta = validation_groups(list(games), games, 0.5)
    assert selected in ({"a1", "b1"}, {"a2", "b2"})
    assert validation_groups(list(reversed(games)), games, 0.5) == (selected, meta)
    assert meta["group_count"] == 2 and meta["eval_group_count"] == 1
    assert {gid for group in meta["eval_groups"] for gid in group["game_ids"]} == selected


def test_unseeded_games_remain_separate_and_one_deal_cannot_be_split() -> None:
    selected, meta = validation_groups(["a", "b"], {}, 0.1)
    assert len(selected) == 1 and meta["group_count"] == 2
    games = {gid: {"game_type": "doudizhu", "metadata": {"deal_seed": 7}} for gid in ("a", "b")}
    with pytest.raises(ValueError, match="two independent"):
        validation_groups(["a", "b"], games, 0.5)
