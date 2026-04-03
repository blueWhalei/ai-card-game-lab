"""Win probability estimation tool."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class WinProbabilityResult:
    """Result of win probability estimation."""

    probability: float
    confidence: str
    factors: list[str]
    reasoning: str


class WinProbabilityTool:
    """Tool for estimating win probability based on game state.

    This tool provides a quick heuristic-based probability estimation
    without requiring LLM calls. It considers:
    - Card count advantage
    - Bomb/rocket possession
    - Turn position
    - Known cards (if any)
    """

    name: str = "win_probability"
    description: str = (
        "估算当前局势的胜率。基于手牌数量、炸弹情况、出牌位置等因素，"
        "返回胜率百分比和关键因素分析。"
    )

    def estimate(
        self,
        my_card_count: int,
        opponent_card_counts: dict[str, int],
        has_bomb: bool = False,
        has_rocket: bool = False,
        is_landlord: bool = False,
        current_turn: int = 0,
    ) -> WinProbabilityResult:
        """Estimate win probability based on game parameters.

        Args:
            my_card_count: Number of cards in my hand
            opponent_card_counts: Dict mapping opponent IDs to their card counts
            has_bomb: Whether I have bombs
            has_rocket: Whether I have rocket (both jokers)
            is_landlord: Whether I am the landlord
            current_turn: Current turn number in the game

        Returns:
            WinProbabilityResult with probability and analysis
        """
        try:
            return self._do_estimation(
                my_card_count=my_card_count,
                opponent_card_counts=opponent_card_counts,
                has_bomb=has_bomb,
                has_rocket=has_rocket,
                is_landlord=is_landlord,
                current_turn=current_turn,
            )
        except Exception as e:
            logger.warning("win_probability_failed", error=str(e), exc_info=True)
            return WinProbabilityResult(
                probability=0.5,
                confidence="低",
                factors=["估算失败"],
                reasoning="无法估算胜率，请手动判断",
            )

    def _do_estimation(
        self,
        my_card_count: int,
        opponent_card_counts: dict[str, int],
        has_bomb: bool,
        has_rocket: bool,
        is_landlord: bool,
        current_turn: int,
    ) -> WinProbabilityResult:
        """Perform the probability estimation."""
        factors: list[str] = []
        probability = 0.5

        min_opponent = min(opponent_card_counts.values()) if opponent_card_counts else 17
        card_advantage = min_opponent - my_card_count

        if my_card_count <= 3:
            probability += 0.25
            factors.append("手牌较少，接近胜利")
        elif my_card_count <= 5:
            probability += 0.15
            factors.append("手牌较少")
        elif my_card_count > 10:
            probability -= 0.1
            factors.append("手牌较多")

        if card_advantage > 0:
            probability += min(0.15, card_advantage * 0.05)
            factors.append(f"手牌优势: 比最少对手少{card_advantage}张")
        elif card_advantage < 0:
            probability -= min(0.15, abs(card_advantage) * 0.03)
            factors.append(f"手牌劣势: 比最少对手多{abs(card_advantage)}张")

        if has_rocket:
            probability += 0.15
            factors.append("有火箭")
        elif has_bomb:
            probability += 0.08
            factors.append("有炸弹")

        if is_landlord:
            probability -= 0.05
            factors.append("地主身份(1v2)")

        if current_turn > 10:
            probability += 0.05
            factors.append("游戏后期，节奏加快")

        probability = max(0.1, min(0.95, probability))

        confidence = self._determine_confidence(probability, len(factors))

        reasoning = self._generate_reasoning(
            probability=probability,
            factors=factors,
            is_landlord=is_landlord,
        )

        return WinProbabilityResult(
            probability=round(probability, 2),
            confidence=confidence,
            factors=factors,
            reasoning=reasoning,
        )

    def _determine_confidence(self, probability: float, factor_count: int) -> str:
        """Determine confidence level of the estimate."""
        if factor_count >= 3:
            return "高"
        elif factor_count >= 1:
            return "中"
        return "低"

    def _generate_reasoning(
        self,
        probability: float,
        factors: list[str],
        is_landlord: bool,
    ) -> str:
        """Generate human-readable reasoning for the estimate."""
        role = "地主" if is_landlord else "农民"

        if probability >= 0.7:
            trend = "胜面较大"
        elif probability >= 0.5:
            trend = "局势均衡"
        else:
            trend = "处于劣势"

        factors_str = "、".join(factors) if factors else "无明显优势劣势"

        return f"作为{role}，{trend}。关键因素：{factors_str}。"
