"""Hand analyzer tool for evaluating hand strength."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.core.engine.doudizhu.cards import (
    BLACK_JOKER,
    RED_JOKER,
    RANK_POWER,
    RANKS,
    card_power,
    sort_cards,
)

logger = structlog.get_logger()


@dataclass(frozen=True)
class HandAnalysis:
    """Result of hand analysis."""

    total_cards: int
    bomb_count: int
    rocket: bool
    high_cards: list[str]
    potential_chains: int
    strength_score: float
    recommendations: list[str]


class HandAnalyzerTool:
    """Tool for analyzing hand strength and potential combinations.

    This tool can be called by AI agents to get a structured analysis
    of their current hand, including:
    - Number of bombs and rockets
    - High card count
    - Chain potential
    - Overall strength score
    - Strategic recommendations
    """

    name: str = "hand_analyzer"
    description: str = (
        "分析当前手牌强度。输入玩家手牌列表,返回手牌强度评分、"
        "炸弹数量、火箭情况、顺子潜力等分析结果。"
    )

    def analyze(self, cards: list[str]) -> HandAnalysis:
        """Analyze the given cards and return structured analysis.

        Args:
            cards: List of card codes like ['S3', 'H4', 'D5', 'BJ', 'RJ']

        Returns:
            HandAnalysis with strength metrics and recommendations
        """
        try:
            return self._do_analysis(cards)
        except Exception as e:
            logger.warning("hand_analysis_failed", error=str(e), exc_info=True)
            return HandAnalysis(
                total_cards=len(cards),
                bomb_count=0,
                rocket=False,
                high_cards=[],
                potential_chains=0,
                strength_score=0.0,
                recommendations=["手牌分析失败,请手动判断"],
            )

    def _do_analysis(self, cards: list[str]) -> HandAnalysis:
        """Perform the actual analysis on the card list."""
        total = len(cards)
        sorted_cards = sort_cards(cards)

        bomb_count = self._count_bombs(sorted_cards)
        rocket = self._has_rocket(sorted_cards)
        high_cards = self._get_high_cards(sorted_cards)
        potential_chains = self._count_potential_chains(sorted_cards)

        strength_score = self._calculate_strength(
            total=total,
            bomb_count=bomb_count,
            rocket=rocket,
            high_card_count=len(high_cards),
            potential_chains=potential_chains,
        )

        recommendations = self._generate_recommendations(
            bomb_count=bomb_count,
            rocket=rocket,
            high_cards=high_cards,
            potential_chains=potential_chains,
            strength_score=strength_score,
        )

        return HandAnalysis(
            total_cards=total,
            bomb_count=bomb_count,
            rocket=rocket,
            high_cards=high_cards,
            potential_chains=potential_chains,
            strength_score=strength_score,
            recommendations=recommendations,
        )

    def _count_bombs(self, cards: list[str]) -> int:
        """Count the number of bombs (4 of a kind) in the hand."""
        count = 0
        ranks: dict[str, int] = {}

        for card in cards:
            if card in (BLACK_JOKER, RED_JOKER):
                continue
            rank = card[1:] if len(card) == 2 else card
            ranks[rank] = ranks.get(rank, 0) + 1

        for _, c in ranks.items():
            if c == 4:
                count += 1

        return count

    def _has_rocket(self, cards: list[str]) -> bool:
        """Check if the hand has a rocket (both jokers)."""
        has_small_joker = False
        has_big_joker = False

        for card in cards:
            if card == BLACK_JOKER:
                has_small_joker = True
            elif card == RED_JOKER:
                has_big_joker = True

        return has_small_joker and has_big_joker

    def _get_high_cards(self, cards: list[str]) -> list[str]:
        """Get high cards (2, A, K, jokers) from the hand."""
        high_ranks = {"2", "A", "K", BLACK_JOKER, RED_JOKER}
        result: list[str] = []
        for card in cards:
            if card in (BLACK_JOKER, RED_JOKER):
                result.append(card)
            elif len(card) == 2 and card[1:] in high_ranks:
                result.append(card)
        return result

    def _count_potential_chains(self, cards: list[str]) -> int:
        """Count potential chain combinations."""
        rank_values: set[int] = set()
        for card in cards:
            if card in (BLACK_JOKER, RED_JOKER):
                continue
            rank = card[1:] if len(card) == 2 else card
            if rank in RANK_POWER:
                rank_values.add(RANK_POWER[rank])

        sorted_values = sorted(rank_values)

        if len(sorted_values) < 5:
            return 0

        chains = 0
        consecutive = 1

        for i in range(1, len(sorted_values)):
            if sorted_values[i] == sorted_values[i - 1] + 1:
                consecutive += 1
            else:
                if consecutive >= 5:
                    chains += 1
                consecutive = 1

        if consecutive >= 5:
            chains += 1

        return chains

    def _calculate_strength(
        self,
        total: int,
        bomb_count: int,
        rocket: bool,
        high_card_count: int,
        potential_chains: int,
    ) -> float:
        """Calculate overall hand strength score (0-100)."""
        score = 0.0

        score += bomb_count * 15
        if rocket:
            score += 20

        score += high_card_count * 5
        score += potential_chains * 3

        if total <= 5:
            score += 10
        elif total <= 10:
            score += 5

        return min(100.0, score)

    def _generate_recommendations(
        self,
        bomb_count: int,
        rocket: bool,
        high_cards: list[str],
        potential_chains: int,
        strength_score: float,
    ) -> list[str]:
        """Generate strategic recommendations based on analysis."""
        recs: list[str] = []

        if strength_score >= 70:
            recs.append("手牌强度很高,可以主动压制")
        elif strength_score >= 40:
            recs.append("手牌强度中等,稳健出牌")
        else:
            recs.append("手牌较弱,以防守为主")

        if bomb_count > 0:
            recs.append(f"有{bomb_count}个炸弹,关键时刻可使用")

        if rocket:
            recs.append("有火箭,最大牌型")

        if potential_chains > 0:
            recs.append(f"有{potential_chains}个顺子潜力,优先组合")

        if len(high_cards) > 3:
            recs.append("大牌较多,注意保留关键牌")

        return recs[:4]
