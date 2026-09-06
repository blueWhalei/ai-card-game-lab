"""Doudizhu analysis tools declared through ``EngineCapability.tools``.

The scoring logic still lives in ``core/ai/tools/hand_analyzer.py``; this module
is the engine-side declaration that lets a policy call it without knowing what a
bomb is.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.core.ai.tools.hand_analyzer import HandAnalyzerTool
from app.core.engine.observation import Observation
from app.core.engine.tools import ToolSpec

_analyzer = HandAnalyzerTool()


def _analyze_hand(observation: Observation, arguments: dict[str, Any]) -> dict[str, Any]:
    """Score the viewer's own hand. Cards come from the observation, not arguments."""
    del arguments
    cards = [str(card) for card in observation.private.get("hand_cards", [])]
    return asdict(_analyzer.analyze(cards))


DOUDIZHU_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="analyze_hand",
        description=(
            "分析你当前手牌的强度：炸弹与火箭数量、大牌、顺子潜力、"
            "综合强度评分与出牌建议。无需参数，自动读取你的手牌。"
        ),
        handler=_analyze_hand,
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    ),
)
