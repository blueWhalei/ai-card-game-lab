"""Expose the viewer’s hand analysis to policies through EngineCapability.tools."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.core.engine.doudizhu.hand_analyzer import HandAnalyzerTool
from app.core.engine.observation import Observation
from app.core.engine.tools import ToolSpec

_analyzer = HandAnalyzerTool()


def _hand_cards(observation: Observation) -> list[str]:
    return [str(card) for card in observation.private.get("hand_cards", [])]


def _analyze_hand(observation: Observation, arguments: dict[str, Any]) -> dict[str, Any]:
    """Score the viewer's own hand. Cards come from the observation, not arguments."""
    del arguments
    analysis = _analyzer.analyze(_hand_cards(observation))
    text = (
        f"**手牌分析**: 启发式规则评分 {analysis.strength_score:.0f}/100（人工权重，非胜率）, "
        f"炸弹 {analysis.bomb_count} 个"
        + (", 有火箭" if analysis.rocket else "")
        + f", 顺子潜力 {analysis.potential_chains} 个"
    )
    if analysis.recommendations:
        text += f"\n**建议**: {'; '.join(analysis.recommendations)}"
    return {"text": text, **asdict(analysis)}


DOUDIZHU_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="analyze_hand",
        description=(
            "分析你当前手牌的特征：炸弹与火箭数量、大牌、顺子潜力、"
            "基于人工权重的启发式评分与建议。评分不是胜率或经过验证的能力量表。"
            "无需参数，自动读取你的手牌。"
        ),
        handler=_analyze_hand,
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    ),
)
