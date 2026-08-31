"""Tests for DoudizhuEngine edge cases and boundary conditions."""

from __future__ import annotations

import pytest

from app.core.engine.doudizhu.cards import ActionType
from app.core.engine.doudizhu.engine import DoudizhuEngine, DoudizhuState
from app.core.engine.base import GameAction
from app.utils.exceptions import InvalidActionError


@pytest.fixture
def engine() -> DoudizhuEngine:
    """Create a DoudizhuEngine instance for testing."""
    return DoudizhuEngine()


@pytest.fixture
def player_ids() -> list[str]:
    """Standard player IDs for testing."""
    return ["player-1", "player-2", "player-3"]


class TestDoudizhuEngineInitialization:
    """Test engine initialization edge cases."""

    def test_player_slot_range_is_three(self, engine: DoudizhuEngine) -> None:
        assert engine.min_players == 3
        assert engine.max_players == 3

    def test_initialize_with_wrong_player_count(self, engine: DoudizhuEngine) -> None:
        """Test initialization fails with wrong number of players."""
        with pytest.raises(InvalidActionError):
            engine.initialize(["p1", "p2"])

        with pytest.raises(InvalidActionError):
            engine.initialize(["p1", "p2", "p3", "p4"])

    def test_initialize_creates_correct_hand_sizes(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> None:
        """Test that initialization creates correct hand sizes."""
        state = engine.initialize(player_ids)

        assert len(state.hands[player_ids[0]]) == 17
        assert len(state.hands[player_ids[1]]) == 17
        assert len(state.hands[player_ids[2]]) == 17
        assert len(state.landlord_cards) == 3

    def test_initialize_starts_in_bidding_phase(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> None:
        """Test that game starts in bidding phase."""
        state = engine.initialize(player_ids)

        assert state.phase == "bidding"
        assert state.bid_order[0] == state.current_player


class TestDoudizhuEngineBiddingPhase:
    """Test bidding phase edge cases."""

    def test_bid_must_exceed_current_highest(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> None:
        """Test that bid must exceed current highest bid."""
        state = engine.initialize(player_ids)
        current_player = state.current_player

        state = engine.apply_action(state, GameAction(
            player_id=current_player,
            action_type=ActionType.BID,
            target="2",
        ))

        next_player = state.current_player
        legal_actions = engine.get_legal_actions(state, next_player)

        bid_1 = [a for a in legal_actions if a.action_type == ActionType.BID and a.target == "1"]
        assert len(bid_1) == 0

        bid_3 = [a for a in legal_actions if a.action_type == ActionType.BID and a.target == "3"]
        assert len(bid_3) == 1

    def test_bid_3_ends_bidding_immediately(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> None:
        """Test that bidding ends immediately when someone bids 3."""
        state = engine.initialize(player_ids)
        current_player = state.current_player

        state = engine.apply_action(state, GameAction(
            player_id=current_player,
            action_type=ActionType.BID,
            target="3",
        ))

        assert state.phase == "playing"
        assert state.roles[current_player] == "landlord"

    def test_all_pass_results_in_no_bid_terminal(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> None:
        """Test that all players passing results in terminal state."""
        state = engine.initialize(player_ids)

        for _ in player_ids:
            current = state.current_player
            state = engine.apply_action(state, GameAction(
                player_id=current,
                action_type=ActionType.BID_PASS,
            ))

        assert state.is_terminal
        assert state.winner_role == "no_bid"

    def test_cannot_bid_out_of_turn(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> None:
        """Test that bidding out of turn raises error."""
        state = engine.initialize(player_ids)

        current = state.current_player
        other = next(pid for pid in player_ids if pid != current)
        with pytest.raises(InvalidActionError):
            engine.apply_action(state, GameAction(
                player_id=other,
                action_type=ActionType.BID,
                target="1",
            ))


class TestDoudizhuEnginePlayingPhase:
    """Test playing phase edge cases."""

    def test_consecutive_passes_reset_last_play(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> None:
        """Test that 2 consecutive passes allow free play."""
        state = self._skip_to_playing_phase(engine, player_ids)

        state = engine.apply_action(state, GameAction(
            player_id=state.current_player,
            action_type=ActionType.PASS,
        ))
        state = engine.apply_action(state, GameAction(
            player_id=state.current_player,
            action_type=ActionType.PASS,
        ))

        legal_actions = engine.get_legal_actions(state, state.current_player)
        pass_actions = [a for a in legal_actions if a.action_type == ActionType.PASS]
        assert len(pass_actions) == 0

    def _skip_to_playing_phase(
        self,
        engine: DoudizhuEngine,
        player_ids: list[str],
    ) -> DoudizhuState:
        """Skip bidding phase to get to playing phase."""
        state = engine.initialize(player_ids)
        current_player = state.current_player
        state = engine.apply_action(state, GameAction(
            player_id=current_player,
            action_type=ActionType.BID,
            target="1",
        ))
        for _ in range(2):
            current = state.current_player
            state = engine.apply_action(state, GameAction(
                player_id=current,
                action_type=ActionType.BID_PASS,
            ))
        return state


class TestDoudizhuEngineParseAction:
    """Test action parsing edge cases."""

    def test_parse_pass_from_json(self, engine: DoudizhuEngine, player_ids: list[str]) -> None:
        """Test parsing PASS action from JSON format."""
        state = engine.initialize(player_ids)
        legal_actions = engine.get_legal_actions(state, state.current_player)

        llm_output = '{"action": {"type": "BID_PASS"}}'
        action = engine.parse_action(llm_output, legal_actions)

        assert action.action_type == ActionType.BID_PASS

    def test_parse_bid_from_json(self, engine: DoudizhuEngine, player_ids: list[str]) -> None:
        """Test parsing BID action from JSON format."""
        state = engine.initialize(player_ids)
        legal_actions = engine.get_legal_actions(state, state.current_player)

        llm_output = '{"action": {"type": "BID", "value": "1"}}'
        action = engine.parse_action(llm_output, legal_actions)

        assert action.action_type == ActionType.BID
        assert action.target == "1"

    def test_parse_fallback_to_first_legal(self, engine: DoudizhuEngine, player_ids: list[str]) -> None:
        """Test that parsing falls back to first legal action on failure."""
        state = engine.initialize(player_ids)
        legal_actions = engine.get_legal_actions(state, state.current_player)

        llm_output = "completely unparseable output"
        action = engine.parse_action(llm_output, legal_actions)

        assert action in legal_actions

    def test_parse_pass_keyword(self, engine: DoudizhuEngine, player_ids: list[str]) -> None:
        """Test parsing PASS from keyword."""
        state = engine.initialize(player_ids)
        legal_actions = engine.get_legal_actions(state, state.current_player)

        llm_output = "我选择不出"
        action = engine.parse_action(llm_output, legal_actions)

        assert action.action_type == ActionType.BID_PASS
