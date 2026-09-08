"""Structured decision protocol: the model returns an action id, not a move.

Asking for ``action_type`` plus ``cards`` means the reply can be well-formed and
still name a move that is not legal, so every consumer needed matching logic and
a fallback. Asking for an ``ActionId`` off the menu removes that class of failure:
either the id is in the legal set or the reply is unusable. Providers that
support JSON Schema get the ids as an ``enum``, which makes an illegal answer
impossible to decode rather than merely detectable.

This parser is game-agnostic on purpose -- it never looks at what an action means.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection
from dataclasses import dataclass

from app.core.engine.base import ActionId
from app.utils.exceptions import AIParseError

_JSON_BLOCK = re.compile(r"\{[^{}]*\}")
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

FORMAT_INSTRUCTIONS = """\
从"可选动作"里选一个，把它的 id **原样**填进 action_id。

输出单行 JSON，不要 markdown 代码块，不要多余文字：
{"thinking":"简短分析1-2句","action_id":"这里填可选动作里的 id"}

action_id 必须与列表中反引号内的字符串完全一致（含大小写、分隔符与空格）。
不要自己编造 id，也不要描述牌面。"""


@dataclass(frozen=True)
class ParsedDecision:
    """A usable reply: an id that is in the legal set."""

    action_id: ActionId
    thinking: str


def response_format(legal_ids: Collection[ActionId]) -> dict[str, object]:
    """OpenAI-style ``response_format`` constraining ``action_id`` to the menu."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "card_game_decision",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "thinking": {"type": "string", "description": "简短分析"},
                    "action_id": {"type": "string", "enum": list(legal_ids)},
                },
                "required": ["thinking", "action_id"],
                "additionalProperties": False,
            },
        },
    }


class ActionIdParser:
    """Extracts ``(action_id, thinking)`` and verifies the id is legal."""

    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, raw_response: str, legal_ids: Collection[ActionId]) -> ParsedDecision:
        """Parse a reply, or raise.

        There is deliberately no fallback to "some legal action": a reply that
        does not name a legal id carries no decision, and pretending otherwise is
        what used to make the parse-success metric report failures as successes.

        Raises:
            AIParseError: no legal id could be read out of the reply.
        """
        legal = set(legal_ids)
        if not legal:
            raise AIParseError("No legal actions to choose from")

        for payload in self._candidate_objects(raw_response):
            chosen = payload.get("action_id")
            if isinstance(chosen, str) and chosen.strip() in legal:
                thinking = payload.get("thinking")
                return ParsedDecision(
                    action_id=chosen.strip(),
                    thinking=str(thinking) if isinstance(thinking, str) else "",
                )

        # No parseable JSON, but the reply may still quote exactly one id verbatim.
        # That is evidence of a choice, not a guess, so it counts as a parse.
        mentioned = [entry for entry in legal if entry in raw_response]
        if len(mentioned) == 1:
            return ParsedDecision(action_id=mentioned[0], thinking=raw_response[:200])

        raise AIParseError(f"No legal action_id in reply (got {raw_response[:120]!r})")

    @staticmethod
    def _candidate_objects(raw_response: str) -> list[dict[str, object]]:
        """Every JSON object the reply might contain, outermost first."""
        candidates: list[str] = [raw_response.strip()]
        candidates.extend(match.strip() for match in _FENCE.findall(raw_response))
        candidates.extend(_JSON_BLOCK.findall(raw_response))

        objects: list[dict[str, object]] = []
        for text in candidates:
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                objects.append(parsed)
        return objects
