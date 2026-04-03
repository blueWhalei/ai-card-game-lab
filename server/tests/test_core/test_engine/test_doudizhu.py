"""Tests for the Doudizhu game engine."""

import json

import pytest

from app.core.engine.base import GameAction
from app.core.engine.doudizhu.cards import ActionType
from app.core.engine.doudizhu.engine import DoudizhuEngine, DoudizhuState
from app.core.ai.prompt import PromptBuilder
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


def test_parse_action_json() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)
    actions = engine.get_legal_actions(state, current)
    # Build a JSON response matching the first non-pass action
    non_pass = [a for a in actions if a.action_type != ActionType.PASS]
    target = non_pass[0]
    llm_output = json.dumps({
        "thinking": "test",
        "action": {"type": str(target.action_type), "cards": list(target.cards)},
    }, ensure_ascii=False)
    parsed = engine.parse_action(llm_output, actions)
    assert sorted(parsed.cards) == sorted(target.cards)


def test_parse_action_bid_json_value() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)
    actions = engine.get_legal_actions(state, current)

    parsed = engine.parse_action(
        '{"thinking": "叫3分", "action": {"type": "BID", "value": 3}}',
        actions,
    )

    assert parsed.action_type == ActionType.BID
    assert parsed.target == "3"


def test_parse_action_bid_json_target() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)
    actions = engine.get_legal_actions(state, current)

    parsed = engine.parse_action(
        '{"thinking": "叫2分", "action": {"type": "BID", "target": 2}}',
        actions,
    )

    assert parsed.action_type == ActionType.BID
    assert parsed.target == "2"


def test_parse_action_bidding_pass() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)
    actions = engine.get_legal_actions(state, current)

    parsed = engine.parse_action(
        '{"thinking": "不叫", "action": {"type": "BID_PASS"}}',
        actions,
    )

    assert parsed.action_type == ActionType.BID_PASS


def test_parse_action_pass() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)
    bid_three = next(
        action
        for action in engine.get_legal_actions(state, current)
        if action.action_type == ActionType.BID and action.target == "3"
    )
    state = engine.apply_action(state, bid_three)
    current = engine.get_current_player(state)
    actions = engine.get_legal_actions(state, current)
    action = next(a for a in actions if a.action_type != ActionType.PASS)
    state = engine.apply_action(state, action)
    next_player = engine.get_current_player(state)
    next_actions = engine.get_legal_actions(state, next_player)
    parsed = engine.parse_action("不出", next_actions)
    assert parsed.action_type == ActionType.PASS


def test_prompt_builder_formats_bid_actions_in_descending_order() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    current = engine.get_current_player(state)
    actions = engine.get_legal_actions(state, current)

    messages = PromptBuilder().build(
        state=state,
        legal_actions=actions,
        engine=engine,
        player_id=current,
    )

    content = messages[1]["content"]
    assert "1. BID 3分（叫3分）" in content
    assert "2. BID 2分（叫2分）" in content
    assert "3. BID 1分（叫1分）" in content
    assert "4. BID_PASS（不叫）" in content


def test_is_terminal_false_initially() -> None:
    engine = DoudizhuEngine()
    state = engine.initialize(["a", "b", "c"])
    assert not engine.is_terminal(state)
    assert engine.get_winner(state) is None
