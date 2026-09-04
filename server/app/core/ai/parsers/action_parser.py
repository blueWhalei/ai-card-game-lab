"""Structured output parser for playing phase actions.

Uses LangChain's PydanticOutputParser to ensure AI responses are
properly formatted and validated before being matched to legal actions.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.core.engine.doudizhu.cards import ActionType

if TYPE_CHECKING:
    from app.core.engine.base import GameAction

# All valid action types for playing phase
PlayingActionType = Literal[
    "PASS",
    "SINGLE",
    "PAIR",
    "TRIPLE",
    "TRIPLE_ONE",
    "TRIPLE_TWO",
    "BOMB",
    "ROCKET",
    "CHAIN",
    "CHAIN_PAIR",
    "AIRPLANE",
    "AIRPLANE_SOLO",
    "AIRPLANE_PAIR",
    "FOUR_TWO",
]


class ActionSchema(BaseModel):
    """Pydantic schema for AI playing action response."""

    thinking: str = Field(
        description="AI 推理过程，分析当前局势、对手牌型、最优策略",
    )
    action_type: PlayingActionType = Field(
        description="动作类型：PASS/SINGLE/PAIR/TRIPLE/TRIPLE_ONE/TRIPLE_TWO/BOMB/ROCKET/CHAIN/CHAIN_PAIR/AIRPLANE/AIRPLANE_SOLO/AIRPLANE_PAIR/FOUR_TWO",
    )
    cards: list[str] = Field(
        default_factory=list,
        description="要出的牌，格式如 ['S3', 'H4', 'D5'] 或 [] (PASS时为空)",
    )


class ActionOutputParser:
    """Parser for AI playing phase responses.

    Wraps LangChain's PydanticOutputParser with:
    - Schema validation
    - Automatic format instructions generation
    - Plain-text parse when the reply is not JSON
    - Legal action matching
    """

    def __init__(self) -> None:
        self._parser = PydanticOutputParser(pydantic_object=ActionSchema)

    def get_format_instructions(self) -> str:
        """Return simplified format instructions to inject into prompt."""
        return """输出 JSON 格式：
```json
{
  "thinking": "简短分析（2-3句）",
  "action_type": "PASS" 或 "SINGLE" 或 "PAIR" 等,
  "cards": ["S3", "H4"] 或 []
}
```

示例 - 出单张：
{"thinking": "出小牌试探", "action_type": "SINGLE", "cards": ["C3"]}

示例 - 不出：
{"thinking": "管不上，让过", "action_type": "PASS", "cards": []}"""

    def parse(
        self,
        raw_response: str,
        legal_actions: list[GameAction],
    ) -> tuple[str, GameAction]:
        """Parse raw LLM response into thinking and a legal action.

        Args:
            raw_response: Raw text from LLM
            legal_actions: List of legal GameAction objects to match against

        Returns:
            Tuple of (thinking_text, matched_legal_action)

        Raises:
            OutputParserException: If parsing fails and no fallback works
        """
        # Try structured parsing first
        try:
            parsed = self._parser.parse(raw_response)
            thinking = parsed.thinking
            action = self._match_to_legal(parsed.action_type, parsed.cards, legal_actions)
            if action is not None:
                return thinking, action
        except OutputParserException:
            pass
        except json.JSONDecodeError:
            pass

        return self._plain_text_parse(raw_response, legal_actions)

    def _match_to_legal(
        self,
        action_type: str,
        cards: list[str],
        legal_actions: list[GameAction],
    ) -> GameAction | None:
        """Match parsed action to a legal action.

        Priority:
        1. Exact match (action_type + cards)
        2. Cards-only match
        3. PASS action type match
        """
        # Handle PASS specially
        if action_type == "PASS":
            for a in legal_actions:
                if a.action_type == "PASS":
                    return a
            return None

        # Try exact match
        for a in legal_actions:
            if (
                str(a.action_type).upper() == action_type.upper()
                and sorted(a.cards) == sorted(cards)
            ):
                return a

        # Try cards-only match (in case action_type was wrong)
        if cards:
            for a in legal_actions:
                if a.action_type != "PASS" and sorted(a.cards) == sorted(cards):
                    return a

        return None

    def _plain_text_parse(
        self,
        raw_response: str,
        legal_actions: list[GameAction],
    ) -> tuple[str, GameAction]:
        """Parse a non-JSON or malformed reply into a legal action."""
        thinking = ""

        # Try to extract thinking from any JSON-like structure
        try:
            json_match = re.search(r"\{[\s\S]*\}", raw_response)
            if json_match:
                data = json.loads(json_match.group())
                thinking = data.get("thinking", "")
        except (json.JSONDecodeError, AttributeError):
            thinking = raw_response[:200]

        # Try to find PASS keyword
        if "不出" in raw_response or "PASS" in raw_response.upper():
            for a in legal_actions:
                if a.action_type == "PASS":
                    return thinking, a

        # Try to find card codes
        card_pattern = re.findall(r"[SHDC][3-9TJQKA2]|BJ|RJ", raw_response)
        if card_pattern:
            for a in legal_actions:
                if a.action_type != ActionType.PASS and sorted(a.cards) == sorted(card_pattern):
                    return thinking, a

        # Last resort: prefer combo types over singles
        # Priority: AIRPLANE_PAIR > AIRPLANE_SOLO > AIRPLANE > FOUR_TWO >
        # CHAIN_PAIR > CHAIN > TRIPLE_TWO > TRIPLE_ONE > TRIPLE > PAIR > SINGLE
        combo_priority = [
            ActionType.AIRPLANE_PAIR,
            ActionType.AIRPLANE_SOLO,
            ActionType.AIRPLANE,
            ActionType.FOUR_TWO,
            ActionType.CHAIN_PAIR,
            ActionType.CHAIN,
            ActionType.TRIPLE_TWO,
            ActionType.TRIPLE_ONE,
            ActionType.TRIPLE,
            ActionType.PAIR,
            ActionType.SINGLE,
        ]
        for priority_type in combo_priority:
            for a in legal_actions:
                if a.action_type == priority_type:
                    return thinking, a

        # Fallback to first non-pass action (should be combo due to sorting)
        non_pass = [a for a in legal_actions if a.action_type != ActionType.PASS]
        if non_pass:
            return thinking, non_pass[0]
        return thinking, legal_actions[0]
