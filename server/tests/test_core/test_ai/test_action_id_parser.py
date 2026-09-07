"""The decision protocol: an id off the menu, or nothing."""

from __future__ import annotations

import pytest

from app.core.ai.parsers.action_id_parser import ActionIdParser, response_format
from app.utils.exceptions import AIParseError

LEGAL = ["SINGLE|C3|", "PAIR|D4 H4|", "PASS||"]


@pytest.fixture
def parser() -> ActionIdParser:
    return ActionIdParser()


def test_a_bare_json_object_is_read(parser: ActionIdParser) -> None:
    decision = parser.parse('{"thinking":"出小牌试探","action_id":"SINGLE|C3|"}', LEGAL)

    assert decision.action_id == "SINGLE|C3|"
    assert decision.thinking == "出小牌试探"


def test_a_fenced_object_is_read(parser: ActionIdParser) -> None:
    raw = '好的，我的决定是：\n```json\n{"thinking":"管不上","action_id":"PASS||"}\n```'

    assert parser.parse(raw, LEGAL).action_id == "PASS||"


def test_an_object_buried_in_prose_is_read(parser: ActionIdParser) -> None:
    raw = '分析：对手牌少。\n{"thinking":"压一手","action_id":"PAIR|D4 H4|"}\n以上。'

    assert parser.parse(raw, LEGAL).action_id == "PAIR|D4 H4|"


def test_an_id_quoted_without_json_still_counts_as_a_choice(parser: ActionIdParser) -> None:
    """Naming exactly one legal id is evidence of a decision, not a guess."""
    decision = parser.parse("我选择 PASS|| 这个动作", LEGAL)

    assert decision.action_id == "PASS||"


def test_an_id_outside_the_legal_set_is_refused(parser: ActionIdParser) -> None:
    with pytest.raises(AIParseError):
        parser.parse('{"thinking":"炸","action_id":"BOMB|S5 H5 D5 C5|"}', LEGAL)


def test_the_old_action_type_format_is_refused(parser: ActionIdParser) -> None:
    """A v1-era reply names a move, not an id, and carries no decision here."""
    with pytest.raises(AIParseError):
        parser.parse('{"thinking":"出单","action_type":"SINGLE","cards":["C3"]}', LEGAL)


def test_unparseable_text_is_refused_rather_than_rescued(parser: ActionIdParser) -> None:
    """No fallback to "some legal action": that is how failures got counted as wins."""
    with pytest.raises(AIParseError):
        parser.parse("我觉得应该出牌，但是让我再想想", LEGAL)


def test_an_ambiguous_reply_naming_two_ids_is_refused(parser: ActionIdParser) -> None:
    with pytest.raises(AIParseError):
        parser.parse("要么 SINGLE|C3| 要么 PASS||，我拿不定", LEGAL)


def test_no_legal_actions_is_refused(parser: ActionIdParser) -> None:
    with pytest.raises(AIParseError):
        parser.parse('{"action_id":"PASS||"}', [])


def test_the_schema_pins_action_id_to_the_legal_set() -> None:
    schema = response_format(LEGAL)["json_schema"]["schema"]  # type: ignore[index]

    assert schema["properties"]["action_id"]["enum"] == LEGAL
    assert schema["required"] == ["thinking", "action_id"]
    assert schema["additionalProperties"] is False
