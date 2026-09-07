"""Tests for the Doudizhu game engine."""

import random

import pytest

from app.core.ai.action_menu import render_menu
from app.core.engine.base import GameAction
from app.core.engine.doudizhu.cards import FULL_DECK, ActionType
from app.core.engine.doudizhu.engine import DoudizhuEngine, DoudizhuState
from app.core.engine.doudizhu.hand_evaluator import classify
from app.utils.exceptions import InvalidActionError


def test_initialize() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["alice", "bob", "charlie"])
    assert isinstance(state, DoudizhuState)
    assert len(state.player_ids) == 3
    # Total cards: 17+17+17+3 landlord bonus = 54
    total_cards = sum(len(h) for h in state.hands.values()) + len(state.landlord_cards)
    assert total_cards == 54
    # Before bidding completes, all players should still have 17 cards
    card_counts = sorted(len(h) for h in state.hands.values())
    assert card_counts == [17, 17, 17]
    # Landlord cards
    assert len(state.landlord_cards) == 3
    assert state.phase == "bidding"
    assert state.current_player == state.bid_order[0]


def test_bidding_legal_actions_only_for_current_player() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])

    current = engine.get_current_player(state)
    other_player = next(pid for pid in state.player_ids if pid != current)

    current_actions = engine.get_legal_actions(state, current)
    other_actions = engine.get_legal_actions(state, other_player)

    assert [action.action_type for action in current_actions] == [
        ActionType.BID_PASS,
        ActionType.BID,
        ActionType.BID,
        ActionType.BID,
    ]
    assert [action.target for action in current_actions if action.action_type == ActionType.BID] == ["1", "2", "3"]
    assert other_actions == []


def test_apply_bid_three_transitions_to_playing_phase() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)
    bid_three = next(
        action
        for action in engine.get_legal_actions(state, current)
        if action.action_type == ActionType.BID and action.target == "3"
    )

    new_state = engine.apply_action(state, bid_three)

    assert new_state.phase == "playing"
    assert new_state.current_player == current
    assert new_state.roles[current] == "landlord"
    assert len(new_state.hands[current]) == 20
    assert new_state.round == 1
    assert new_state.turn_order[0] == current


def test_apply_bid_pass_all_players_marks_no_bid_terminal() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])

    for expected_round in (1, 2, 3):
        current = engine.get_current_player(state)
        bid_pass = next(
            action
            for action in engine.get_legal_actions(state, current)
            if action.action_type == ActionType.BID_PASS
        )
        state = engine.apply_action(state, bid_pass)
        assert state.round == expected_round

    assert state.is_terminal is True
    assert state.winner is None
    assert state.winner_role == "no_bid"
    assert state.phase == "bidding"


def test_apply_bid_rejects_bid_not_exceeding_current_highest() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])

    current = engine.get_current_player(state)
    bid_two = next(
        action
        for action in engine.get_legal_actions(state, current)
        if action.action_type == ActionType.BID and action.target == "2"
    )
    state = engine.apply_action(state, bid_two)

    next_player = engine.get_current_player(state)
    invalid_bid = GameAction(player_id=next_player, action_type=ActionType.BID, cards=[], target="2")

    with pytest.raises(InvalidActionError):
        engine.apply_action(state, invalid_bid)







def test_the_bid_menu_offers_the_highest_bid_first() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)

    presented, omitted = engine.present_legal_actions(state, current)
    menu = render_menu(presented, omitted)

    assert omitted == 0
    assert [entry.label for entry in presented] == [
        "BID 3分（叫3分）",
        "BID 2分（叫2分）",
        "BID 1分（叫1分）",
        "BID_PASS（不叫）",
    ]
    # Each line carries the id the model has to echo back.
    assert "`BID||3` — BID 3分（叫3分）" in menu


def test_a_truncated_menu_still_offers_every_action_type() -> None:
    """A hand with hundreds of plays must not lose PASS to the 80-line cap.

    PASS sorts last by presentation priority, so plain truncation would drop the
    one action that is always available.
    """
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    state = engine.apply_action(
        state,
        next(
            action
            for action in engine.get_legal_actions(state, engine.get_current_player(state))
            if action.action_type == ActionType.BID and action.target == "3"
        ),
    )
    landlord = engine.get_current_player(state)
    # Someone has to have played for PASS to be legal at all.
    first_play = next(
        action
        for action in engine.get_legal_actions(state, landlord)
        if action.action_type == ActionType.SINGLE
    )
    state = engine.apply_action(state, first_play)
    responder = engine.get_current_player(state)

    all_legal = engine.legal_actions(state, responder)
    presented, omitted = engine.present_legal_actions(state, responder, limit=3)

    assert len(presented) == 3
    assert omitted == len(all_legal) - 3
    assert any(entry.action.action_type == ActionType.PASS for entry in presented)


def test_is_terminal_false_initially() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    assert not engine.is_terminal(state)
    assert engine.get_winner(state) is None


def _advance(engine: DoudizhuEngine, state: DoudizhuState, steps: int) -> DoudizhuState:
    """Take the first legal action ``steps`` times (bidding starts with BID 3)."""
    for _ in range(steps):
        if engine.is_terminal(state):
            break
        player_id = engine.get_current_player(state)
        actions = engine.legal_actions(state, player_id)
        state = engine._cast(engine.apply_action(state, actions[0].action))
    return state


def test_sample_hidden_state_keeps_the_deck_consistent() -> None:
    engine = DoudizhuEngine()
    state = _advance(engine, engine.initialize(["a", "b", "c"], seed=7), 4)
    assert state.phase == "playing"

    viewer = next(pid for pid, role in state.roles.items() if role == "peasant")
    obs = engine.observe(state, viewer)
    sampled = engine.sample_hidden_state(obs, random.Random(99))

    assert sampled.hands[viewer] == state.hands[viewer]
    assert {pid: len(h) for pid, h in sampled.hands.items()} == {
        pid: len(h) for pid, h in state.hands.items()
    }

    played = [card for entry in state.play_history for card in entry.get("cards", [])]
    all_cards = [card for hand in sampled.hands.values() for card in hand] + played
    assert sorted(all_cards) == sorted(FULL_DECK)

    landlord = next(pid for pid, role in state.roles.items() if role == "landlord")
    unplayed_bottom = set(state.landlord_cards) - set(played)
    assert unplayed_bottom <= set(sampled.hands[landlord])


def test_sample_hidden_state_hides_the_bottom_cards_during_bidding() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"], seed=11)
    obs = engine.observe(state, "a")

    assert "landlord_cards" not in obs.public

    sampled = engine.sample_hidden_state(obs, random.Random(3))
    assert sampled.hands["a"] == state.hands["a"]
    assert len(sampled.landlord_cards) == 3
    all_cards = [c for hand in sampled.hands.values() for c in hand] + sampled.landlord_cards
    assert sorted(all_cards) == sorted(FULL_DECK)


def _playing_state(
    hands: dict[str, list[str]],
    *,
    last_play: tuple[str, ActionType, int, list[str]] | None = None,
) -> DoudizhuState:
    return DoudizhuState(
        game_type="doudizhu",
        round=5,
        player_ids=["a", "b", "c"],
        current_player="a",
        is_terminal=False,
        hands=hands,
        roles={"a": "landlord", "b": "peasant", "c": "peasant"},
        landlord_cards=[],
        last_play=last_play,
        consecutive_passes=0,
        play_history=[],
        turn_order=["a", "b", "c"],
        current_turn_index=0,
        phase="playing",
    )


def _suggested(engine: DoudizhuEngine, state: DoudizhuState) -> GameAction:
    legal = engine.legal_actions(state, "a")
    suggestion = engine.suggest_action(engine.observe(state, "a"), legal)
    assert suggestion is not None
    return engine.resolve_action(state, "a", suggestion)


def test_heuristic_leads_with_the_cheapest_play() -> None:
    engine = DoudizhuEngine()
    state = _playing_state(
        {
            "a": ["S3", "H4", "S5", "S6", "H6", "D6", "C6"],
            "b": ["S7", "H7"],
            "c": ["S8", "H8"],
        }
    )

    action = _suggested(engine, state)

    assert action.action_type == ActionType.SINGLE
    assert action.cards == ["S3"]


def test_heuristic_keeps_its_bomb_when_nobody_is_close_to_finishing() -> None:
    engine = DoudizhuEngine()
    single_seven = classify(["S7"])
    assert single_seven is not None
    state = _playing_state(
        {
            "a": ["S6", "H6", "D6", "C6"],
            "b": ["S9", "H9", "D9", "ST", "HT"],
            "c": ["SJ", "HJ", "DJ", "SQ", "HQ"],
        },
        last_play=("b", single_seven[0], single_seven[1], ["S7"]),
    )

    action = _suggested(engine, state)

    assert action.action_type == ActionType.PASS


def test_heuristic_spends_the_bomb_to_stop_an_opponent() -> None:
    engine = DoudizhuEngine()
    single_seven = classify(["S7"])
    assert single_seven is not None
    state = _playing_state(
        {"a": ["S6", "H6", "D6", "C6"], "b": ["S9"], "c": ["SJ", "HJ"]},
        last_play=("b", single_seven[0], single_seven[1], ["S7"]),
    )

    action = _suggested(engine, state)

    assert action.action_type == ActionType.BOMB


def _finished_state(winner: str, roles: dict[str, str]) -> DoudizhuState:
    return DoudizhuState(
        game_type="doudizhu",
        round=10,
        player_ids=["a", "b", "c"],
        current_player=winner,
        is_terminal=True,
        winner=winner,
        winner_role=roles[winner],
        roles=roles,
    )


def test_terminal_rewards_pay_the_whole_winning_side() -> None:
    engine = DoudizhuEngine()
    roles = {"a": "landlord", "b": "peasant", "c": "peasant"}

    landlord_win = engine.terminal_rewards(_finished_state("a", roles))
    assert landlord_win == {"a": 1.0, "b": 0.0, "c": 0.0}

    peasant_win = engine.terminal_rewards(_finished_state("b", roles))
    assert peasant_win == {"a": 0.0, "b": 1.0, "c": 1.0}


def test_terminal_rewards_pay_nothing_on_a_no_bid_redeal() -> None:
    engine = DoudizhuEngine()
    state = DoudizhuState(
        game_type="doudizhu",
        round=3,
        player_ids=["a", "b", "c"],
        current_player="a",
        is_terminal=True,
        winner=None,
        winner_role="no_bid",
    )

    assert engine.terminal_rewards(state) == {"a": 0.0, "b": 0.0, "c": 0.0}
