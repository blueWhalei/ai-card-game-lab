"""Structured output parser for bidding phase actions.

Uses LangChain's PydanticOutputParser to ensure AI responses for
the bidding phase are properly formatted and validated.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.core.engine.base import GameAction

# Valid bidding action types
BiddingActionType = Literal["BID", "BID_PASS"]


class BidSchema(BaseModel):
    """Pydantic schema for AI bidding response."""

    thinking: str = Field(
        description="你对手牌的分析和叫分理由",
    )
    action_type: BiddingActionType = Field(
        description="动作类型：BID（叫分）或 BID_PASS（不叫）",
    )
    value: int | None = Field(
        default=None,
        description="叫分值（1/2/3），仅 BID 时需要；BID_PASS 时为 null",
    )


class BidOutputParser:
    """Parser for AI bidding phase responses.

    Wraps LangChain's PydanticOutputParser with:
    - Schema validation
    - Bid value validation (1-3)
    - Legal action matching
    - Plain-text parse when the reply is not JSON
    """

    def __init__(self) -> None:
        self._parser = PydanticOutputParser(pydantic_object=BidSchema)

    def get_format_instructions(self) -> str:
        """Return simplified format instructions to inject into prompt."""
        return """输出 JSON 格式：
```json
{
  "thinking": "简短分析（1-2句）",
  "action_type": "BID" 或 "BID_PASS",
  "value": 1 或 2 或 3（仅 BID 时）或 null（BID_PASS 时）
}
```

示例 - 叫3分：
{"thinking": "有炸弹，牌强", "action_type": "BID", "value": 3}

示例 - 不叫：
{"thinking": "牌散无大牌", "action_type": "BID_PASS", "value": null}"""

    def parse(
        self,
        raw_response: str,
        legal_actions: list[GameAction],
    ) -> tuple[str, GameAction]:
        """Parse raw LLM response into thinking and a legal bidding action.

        Args:
            raw_response: Raw text from LLM
            legal_actions: List of legal GameAction objects (BID/BID_PASS)

        Returns:
            Tuple of (thinking_text, matched_legal_action)

        Raises:
            OutputParserException: If parsing fails and no fallback works
        """
        # Try structured parsing first
        try:
            parsed = self._parser.parse(raw_response)
            thinking = parsed.thinking
            action = self._match_to_legal(
                parsed.action_type,
                parsed.value,
                legal_actions,
            )
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
        value: int | None,
        legal_actions: list[GameAction],
    ) -> GameAction | None:
        """Match parsed bidding action to a legal action."""
        action_upper = action_type.upper()

        # Handle BID_PASS
        if action_upper == "BID_PASS":
            for a in legal_actions:
                if str(a.action_type).upper() == "BID_PASS":
                    return a
            return None

        # Handle BID with specific value
        if action_upper == "BID" and value is not None:
            for a in legal_actions:
                if (
                    str(a.action_type).upper() == "BID"
                    and a.target == str(value)
                ):
                    return a
            # Fallback: any BID action if value doesn't match
            for a in legal_actions:
                if str(a.action_type).upper() == "BID":
                    return a

        return None

    def _plain_text_parse(
        self,
        raw_response: str,
        legal_actions: list[GameAction],
    ) -> tuple[str, GameAction]:
        """Parse a non-JSON bidding reply into a legal action."""
        thinking = ""

        # Try to extract thinking from any JSON-like structure
        try:
            json_match = re.search(r"\{[\s\S]*\}", raw_response)
            if json_match:
                data = json.loads(json_match.group())
                thinking = data.get("thinking", "")

                # Try to parse action
                action_data = data.get("action", data)
                action_type = str(
                    action_data.get("type", action_data.get("action_type", ""))
                ).upper()
                value = action_data.get("value", action_data.get("target", 0))

                # Match BID_PASS - only check action_type, NOT raw_response
                # (raw_response may contain "不叫" in reasoning about rules)
                if action_type == "BID_PASS":
                    for a in legal_actions:
                        if str(a.action_type).upper() == "BID_PASS":
                            return thinking, a

                # Match BID with specific value
                if action_type == "BID":
                    for a in legal_actions:
                        if (
                            str(a.action_type).upper() == "BID"
                            and a.target == str(value)
                        ):
                            return thinking, a
                    # Fallback: any BID action if value doesn't match
                    for a in legal_actions:
                        if str(a.action_type).upper() == "BID":
                            return thinking, a

                # If action_type parsed but not recognized, fall through to keyword fallback
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            thinking = raw_response[:200]

        # Keyword fallback - only used when JSON parsing failed
        if "不叫" in raw_response or "PASS" in raw_response.upper():
            for a in legal_actions:
                if str(a.action_type).upper() == "BID_PASS":
                    return thinking, a

        # Last resort: first BID action or BID_PASS
        for a in legal_actions:
            if str(a.action_type).upper() == "BID":
                return thinking, a
        return thinking, legal_actions[0]
