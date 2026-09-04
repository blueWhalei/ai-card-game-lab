"""Unit tests for LangChain-based output parsers."""

from __future__ import annotations

import pytest

from app.core.ai.parsers.action_parser import ActionOutputParser
from app.core.ai.parsers.bid_parser import BidOutputParser
from app.core.engine.base import GameAction
from app.core.engine.doudizhu.cards import ActionType


class TestActionOutputParser:
    """Test cases for ActionOutputParser."""

    @pytest.fixture
    def parser(self) -> ActionOutputParser:
        return ActionOutputParser()

    @pytest.fixture
    def legal_playing_actions(self) -> list[GameAction]:
        """Sample legal actions for playing phase."""
        return [
            GameAction(player_id="p1", action_type=ActionType.PASS),
            GameAction(player_id="p1", action_type=ActionType.SINGLE, cards=["S3"]),
            GameAction(player_id="p1", action_type=ActionType.PAIR, cards=["S3", "H3"]),
            GameAction(player_id="p1", action_type=ActionType.TRIPLE, cards=["S3", "H3", "D3"]),
            GameAction(player_id="p1", action_type=ActionType.BOMB, cards=["S5", "H5", "D5", "C5"]),
        ]

    def test_get_format_instructions(self, parser: ActionOutputParser) -> None:
        """Format instructions should be non-empty and contain JSON schema."""
        instructions = parser.get_format_instructions()
        assert instructions
        assert "JSON" in instructions or "json" in instructions

    def test_parse_valid_json_single(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Should parse valid JSON with SINGLE action."""
        raw = '{"thinking": "分析对手牌型", "action_type": "SINGLE", "cards": ["S3"]}'
        thinking, action = parser.parse(raw, legal_playing_actions)

        assert thinking == "分析对手牌型"
        assert action.action_type == ActionType.SINGLE
        assert action.cards == ["S3"]

    def test_parse_valid_json_pair(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Should parse valid JSON with PAIR action."""
        raw = '{"thinking": "出对子控场", "action_type": "PAIR", "cards": ["S3", "H3"]}'
        thinking, action = parser.parse(raw, legal_playing_actions)

        assert thinking == "出对子控场"
        assert action.action_type == ActionType.PAIR
        assert sorted(action.cards) == sorted(["S3", "H3"])

    def test_parse_valid_json_pass(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Should parse valid JSON with PASS action."""
        raw = '{"thinking": "等待更好时机", "action_type": "PASS", "cards": []}'
        thinking, action = parser.parse(raw, legal_playing_actions)

        assert thinking == "等待更好时机"
        assert action.action_type == ActionType.PASS
        assert action.cards == []

    def test_parse_json_with_markdown_wrapper(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Should parse JSON wrapped in markdown code block."""
        raw = '''```json
{"thinking": "炸弹压制", "action_type": "BOMB", "cards": ["S5", "H5", "D5", "C5"]}
```'''
        thinking, action = parser.parse(raw, legal_playing_actions)

        assert "炸弹压制" in thinking
        assert action.action_type == ActionType.BOMB

    def test_parse_cards_only_match(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Should match by cards even if action_type differs."""
        # Even if action_type is wrong, should match by cards
        raw = '{"thinking": "出牌", "action_type": "SINGLE", "cards": ["S3", "H3"]}'
        thinking, action = parser.parse(raw, legal_playing_actions)

        # Should fallback to cards-only match (PAIR)
        assert action.cards == ["S3", "H3"] or action.action_type == ActionType.PAIR

    def test_parse_plain_text_pass(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Parse non-JSON text that contains PASS."""
        raw = "我选择不出"
        thinking, action = parser.parse(raw, legal_playing_actions)

        assert action.action_type == ActionType.PASS

    def test_parse_plain_text_cards(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Parse non-JSON text that contains card codes."""
        raw = "我想出 S3"
        thinking, action = parser.parse(raw, legal_playing_actions)

        assert action.action_type == ActionType.SINGLE
        assert action.cards == ["S3"]

    def test_parse_invalid_json_fallback(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Should fallback to first non-pass action for unparseable input."""
        raw = "完全无法解析的文本"
        thinking, action = parser.parse(raw, legal_playing_actions)

        # Should return some legal action
        assert action in legal_playing_actions

    def test_parse_empty_cards_pass(self, parser: ActionOutputParser, legal_playing_actions: list[GameAction]) -> None:
        """Should handle PASS with empty cards."""
        raw = '{"thinking": "跳过", "action_type": "PASS"}'
        thinking, action = parser.parse(raw, legal_playing_actions)

        assert action.action_type == ActionType.PASS


class TestBidOutputParser:
    """Test cases for BidOutputParser."""

    @pytest.fixture
    def parser(self) -> BidOutputParser:
        return BidOutputParser()

    @pytest.fixture
    def legal_bid_actions(self) -> list[GameAction]:
        """Sample legal actions for bidding phase."""
        return [
            GameAction(player_id="p1", action_type=ActionType.BID_PASS),
            GameAction(player_id="p1", action_type=ActionType.BID, target="1"),
            GameAction(player_id="p1", action_type=ActionType.BID, target="2"),
            GameAction(player_id="p1", action_type=ActionType.BID, target="3"),
        ]

    def test_get_format_instructions(self, parser: BidOutputParser) -> None:
        """Format instructions should be non-empty."""
        instructions = parser.get_format_instructions()
        assert instructions

    def test_parse_valid_bid_1(self, parser: BidOutputParser, legal_bid_actions: list[GameAction]) -> None:
        """Should parse valid BID action with value 1."""
        raw = '{"thinking": "手牌一般，叫1分", "action_type": "BID", "value": 1}'
        thinking, action = parser.parse(raw, legal_bid_actions)

        assert thinking == "手牌一般，叫1分"
        assert action.action_type == ActionType.BID
        assert action.target == "1"

    def test_parse_valid_bid_3(self, parser: BidOutputParser, legal_bid_actions: list[GameAction]) -> None:
        """Should parse valid BID action with value 3."""
        raw = '{"thinking": "有炸弹，叫3分", "action_type": "BID", "value": 3}'
        thinking, action = parser.parse(raw, legal_bid_actions)

        assert "有炸弹" in thinking
        assert action.action_type == ActionType.BID
        assert action.target == "3"

    def test_parse_valid_bid_pass(self, parser: BidOutputParser, legal_bid_actions: list[GameAction]) -> None:
        """Should parse valid BID_PASS action."""
        raw = '{"thinking": "手牌太弱，不叫", "action_type": "BID_PASS"}'
        thinking, action = parser.parse(raw, legal_bid_actions)

        assert "手牌太弱" in thinking
        assert action.action_type == ActionType.BID_PASS

    def test_parse_plain_text_pass(self, parser: BidOutputParser, legal_bid_actions: list[GameAction]) -> None:
        """Parse non-JSON text that contains 不叫."""
        raw = "手牌太弱，我选择不叫"
        thinking, action = parser.parse(raw, legal_bid_actions)

        assert action.action_type == ActionType.BID_PASS

    def test_parse_plain_text_bid(self, parser: BidOutputParser, legal_bid_actions: list[GameAction]) -> None:
        """Parse non-JSON text that contains a bid value."""
        raw = '{"thinking": "叫2分", "action": {"type": "BID", "value": 2}}'
        thinking, action = parser.parse(raw, legal_bid_actions)

        assert action.action_type == ActionType.BID
        assert action.target == "2"

    def test_parse_invalid_fallback(self, parser: BidOutputParser, legal_bid_actions: list[GameAction]) -> None:
        """Should fallback to first BID action for unparseable input."""
        raw = "完全无法解析的文本"
        thinking, action = parser.parse(raw, legal_bid_actions)

        # Should return some legal action (preferably BID over BID_PASS)
        assert action in legal_bid_actions

    def test_parse_bid_value_not_in_legal(self, parser: BidOutputParser, legal_bid_actions: list[GameAction]) -> None:
        """Should fallback to any BID if specific value not in legal actions."""
        # If value 5 is not legal, should return any available BID
        raw = '{"thinking": "叫5分", "action_type": "BID", "value": 5}'
        # Legal actions only have 1, 2, 3
        thinking, action = parser.parse(raw, legal_bid_actions)

        # Should return some BID action
        assert action.action_type == ActionType.BID


class TestParserEdgeCases:
    """Edge case tests for parsers."""

    @pytest.fixture
    def action_parser(self) -> ActionOutputParser:
        return ActionOutputParser()

    @pytest.fixture
    def bid_parser(self) -> BidOutputParser:
        return BidOutputParser()

    def test_action_parser_empty_legal_actions(self, action_parser: ActionOutputParser) -> None:
        """Should handle empty legal actions gracefully."""
        # This should not crash, but behavior is undefined
        raw = '{"thinking": "test", "action_type": "PASS"}'
        # Empty list should still work for PASS
        try:
            thinking, action = action_parser.parse(raw, [])
        except (IndexError, KeyError):
            # Expected for empty list
            pass

    def test_bid_parser_single_action(self, bid_parser: BidOutputParser) -> None:
        """Should handle single legal action."""
        single_action = [GameAction(player_id="p1", action_type=ActionType.BID_PASS)]
        raw = '{"thinking": "不叫", "action_type": "BID_PASS"}'
        thinking, action = bid_parser.parse(raw, single_action)

        assert action.action_type == ActionType.BID_PASS

    def test_action_parser_malformed_json(self, action_parser: ActionOutputParser) -> None:
        """Should handle malformed JSON gracefully."""
        legal = [GameAction(player_id="p1", action_type=ActionType.PASS)]
        raw = '{"thinking": "unclosed'

        # Should not crash, should fallback
        thinking, action = action_parser.parse(raw, legal)
        assert action in legal

    def test_action_parser_unicode_cards(self, action_parser: ActionOutputParser) -> None:
        """Should handle card codes correctly."""
        legal = [
            GameAction(player_id="p1", action_type=ActionType.ROCKET, cards=["BJ", "RJ"]),
        ]
        raw = '{"thinking": "王炸", "action_type": "ROCKET", "cards": ["BJ", "RJ"]}'
        thinking, action = action_parser.parse(raw, legal)

        assert action.action_type == ActionType.ROCKET
        assert sorted(action.cards) == ["BJ", "RJ"]
