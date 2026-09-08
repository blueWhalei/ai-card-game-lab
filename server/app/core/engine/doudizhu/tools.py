"""Doudizhu analysis tools declared through ``EngineCapability.tools``.

The scoring logic lives in ``hand_analyzer`` / ``win_probability`` helpers; this
module is the engine-side declaration that lets a policy call them without knowing
what a bomb is. Each handler returns a ``text`` line for prompt injection plus the
structured fields behind it.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.core.ai.tools.win_probability import WinProbabilityTool
from app.core.engine.doudizhu.hand_analyzer import HandAnalyzerTool
from app.core.engine.observation import Observation
from app.core.engine.tools import ToolSpec

_analyzer = HandAnalyzerTool()
_win_probability = WinProbabilityTool()


def _hand_cards(observation: Observation) -> list[str]:
    return [str(card) for card in observation.private.get("hand_cards", [])]


def _analyze_hand(observation: Observation, arguments: dict[str, Any]) -> dict[str, Any]:
    """Score the viewer's own hand. Cards come from the observation, not arguments."""
    del arguments
    analysis = _analyzer.analyze(_hand_cards(observation))
    text = (
        f"**手牌分析**: 强度 {analysis.strength_score:.0f}/100, "
        f"炸弹 {analysis.bomb_count} 个"
        + (", 有火箭" if analysis.rocket else "")
        + f", 顺子潜力 {analysis.potential_chains} 个"
    )
    if analysis.recommendations:
        text += f"\n**建议**: {'; '.join(analysis.recommendations)}"
    return {"text": text, **asdict(analysis)}


def _estimate_win_probability(
    observation: Observation, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Rough win-rate estimate from card counts, roles, and bomb holdings."""
    del arguments
    cards = _hand_cards(observation)
    hand_counts = observation.public.get("hand_counts") or {}
    opponent_counts = {
        pid: int(count) for pid, count in hand_counts.items() if pid != observation.player_id
    }
    roles = observation.public.get("roles") or {}
    analysis = _analyzer.analyze(cards)

    result = _win_probability.estimate(
        my_card_count=len(cards),
        opponent_card_counts=opponent_counts,
        has_bomb=analysis.bomb_count > 0,
        has_rocket=analysis.rocket,
        is_landlord=roles.get(observation.player_id) == "landlord",
        current_turn=observation.round,
    )
    text = f"**胜率估算**: {result.probability * 100:.0f}% (置信度: {result.confidence})"
    if result.reasoning:
        text += f"\n**分析**: {result.reasoning}"
    return {"text": text, **asdict(result)}


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
    ToolSpec(
        name="win_probability",
        description=(
            "根据手牌张数、对手剩余张数、炸弹持有情况与身份估算当前胜率。"
            "无需参数，自动读取局面信息。"
        ),
        handler=_estimate_win_probability,
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        # Roles are not assigned during bidding, so a win-rate estimate would be
        # guessing at which side it is estimating for.
        phases=("playing",),
    ),
)
