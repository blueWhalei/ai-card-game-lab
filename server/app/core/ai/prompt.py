"""Prompt construction utilities for LLM-based game agents.

This module provides:
- PromptBuilder: Builds prompts from game state using templates
- PromptTemplateRegistry: Manages prompt versions and A/B testing
- Integration with LangChain parsers for structured output
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.ai.parsers.action_parser import ActionOutputParser
from app.core.ai.parsers.bid_parser import BidOutputParser
from app.core.ai.prompts.registry import PromptTemplateRegistry
from app.core.engine.doudizhu.cards import ActionType, sort_cards

if TYPE_CHECKING:
    import aiosqlite

    from app.core.ai.tools.hand_analyzer import HandAnalysis
    from app.core.ai.tools.win_probability import WinProbabilityResult
    from app.core.engine.base import GameAction, GameEngine, GameState

# ── Reasoning model detection ──────────────────────────────────────────────────
# Models that output chain-of-thought reasoning before the final answer
REASONING_MODEL_PATTERNS = [
    r"deepseek-v4-pro",
    r"deepseek-reasoner",  # legacy alias (retired)
    r"deepseek-r1",
    r"o1-mini",
    r"o1-preview",
    r"o1",
    r"claude-3-5-sonnet.*thinking",
    r"claude-3-7",
    r"claude-4.*thinking",
    r"qwen.*thinking",
    r"qwen-qwq",
    r"qwq",
]


def is_reasoning_model(model_name: str | None) -> bool:
    """Check if the model is a reasoning/thinking model.

    Reasoning models output chain-of-thought before the final answer,
    and require different prompt templates.
    """
    if not model_name:
        return False
    model_lower = model_name.lower()
    return any(re.search(pattern, model_lower) for pattern in REASONING_MODEL_PATTERNS)

# ── Action type priority for sorting (higher = shown first) ─────────────────
ACTION_PRIORITY: dict[str, int] = {
    ActionType.ROCKET: 14,
    ActionType.BOMB: 13,
    ActionType.AIRPLANE_PAIR: 12,
    ActionType.AIRPLANE_SOLO: 11,
    ActionType.AIRPLANE: 10,
    ActionType.FOUR_TWO: 9,
    ActionType.CHAIN_PAIR: 8,
    ActionType.CHAIN: 7,
    ActionType.TRIPLE_TWO: 6,
    ActionType.TRIPLE_ONE: 5,
    ActionType.TRIPLE: 4,
    ActionType.PAIR: 3,
    ActionType.SINGLE: 2,
    ActionType.PASS: 1,
    ActionType.BID_PASS: 0,
    ActionType.BID: 13,  # bids shown prominently
}

# Legacy templates (used as fallback)
SYSTEM_TEMPLATE = """\
你是斗地主 AI 玩家。你的玩家ID会在每轮提示中明确标注。

## 核心规则
- 地主(20张) vs 两农民(各17张)，先出完手牌者获胜
- 牌力：3<4<5<6<7<8<9<10<J<Q<K<A<2<小王<大王
- 出牌必须比上家大（同牌型比点数），或选择PASS
- 炸弹/火箭可压制任何牌型

## 决策要点
- 地主：主动压制，优先出组合牌型
- 农民：配合队友，队友牌少时让牌，地主牌少时管牌

{format_instructions}

## 输出格式（严格遵守）
直接输出单行 JSON，无 markdown 代码块，无额外文字：
{{"thinking":"简短分析1-2句","action_type":"动作类型","cards":["牌1","牌2"]}}

牌面编码：S=黑桃 H=红心 D=方块 C=梅花，BJ=小王，RJ=大王
"""

BIDDING_SYSTEM_TEMPLATE = """\
你是斗地主 AI 玩家，正在进行叫地主阶段。

## 叫地主规则
- 可叫1/2/3分或选择 BID_PASS，叫分必须高于当前最高
- 叫3分立即成为地主（获得3张底牌，共20张）
- 三人都选 BID_PASS 则重新发牌

## 手牌评估
| 条件 | 叫分 |
|------|------|
| 有炸弹/王炸 或 ≥2张2 | 3分 |
| 有1张2 + 牌型好 | 2分 |
| 牌型一般但有大牌 | 1分 |
| 牌散且无大牌 | BID_PASS |

{format_instructions}

## 输出格式（严格遵守）
直接输出单行 JSON，无 markdown 代码块，无额外文字：
{{"thinking":"简短分析1-2句","action_type":"BID或BID_PASS","value":1或2或3或null}}
"""


def _load_rules(game_type: str) -> str:
    """Load game rules from docs markdown file, fallback to inline."""
    rules_path = Path(__file__).parents[4] / "docs" / "欢乐斗地主经典玩法规则.md"
    if rules_path.exists():
        return rules_path.read_text(encoding="utf-8")
    return FALLBACK_RULES.get(game_type, "")


FALLBACK_RULES: dict[str, str] = {
    "doudizhu": """\
斗地主是一种三人纸牌游戏，使用一副54张牌。
- 一人为"地主"，另外两人为"农民"，农民合作对抗地主
- 地主有20张牌（17张+3张底牌），农民各有17张牌
- 地主先出牌，按顺序轮流出牌
- 出牌必须比上家大（相同牌型且点数更高），或者选择"不出"
- 炸弹可以压制任何非炸弹/火箭牌型，火箭（双王）最大
- 谁先出完所有手牌谁赢
- 牌力大小：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2 < 小王 < 大王\
""",
}

GAME_TYPE_CN: dict[str, str] = {
    "doudizhu": "斗地主",
}

# Cache loaded rules
_rules_cache: dict[str, str] = {}

# Parser instances (shared across all PromptBuilder instances)
_action_parser = ActionOutputParser()
_bid_parser = BidOutputParser()

# Global registry instance (initialized with defaults)
_registry = PromptTemplateRegistry()


def get_prompt_registry() -> PromptTemplateRegistry:
    """Get the global prompt template registry."""
    return _registry


class PromptBuilder:
    """Builds structured prompts from game state and legal actions.

    Features:
    - Version-controlled prompt templates via Registry
    - A/B testing support
    - LangChain parser integration for structured output
    - Automatic reasoning model detection
    """

    def __init__(
        self,
        registry: PromptTemplateRegistry | None = None,
        default_version: str = "v1",
    ) -> None:
        self._registry = registry or _registry
        self._default_version = default_version

    def _select_version_for_model(self, model_name: str | None) -> str:
        """Select appropriate template version based on model type.

        Args:
            model_name: The model identifier (e.g., "deepseek-v4-flash", "gpt-4o")

        Returns:
            Template version to use ("v1", "v2", or "reasoning")
        """
        if is_reasoning_model(model_name):
            return "reasoning"
        return self._default_version

    async def build_async(
        self,
        state: GameState,
        legal_actions: list[GameAction],
        engine: GameEngine,
        player_id: str,
        db: aiosqlite.Connection | None = None,
        session_id: str | None = None,
        model_name: str | None = None,
        tool_analysis: str | None = None,
    ) -> list[dict[str, str]]:
        """Build prompt asynchronously with database support.

        This is the preferred method when database access is available.

        Args:
            state: Current game state
            legal_actions: List of legal actions
            engine: Game engine instance
            player_id: ID of the player making the decision
            db: Optional database connection for template persistence
            session_id: Optional session ID for A/B testing
            model_name: Optional model name to select appropriate template version
            tool_analysis: Optional pre-formatted tool analysis text to inject
        """
        game_type = state.game_type
        version = self._select_version_for_model(model_name)

        # Check if in bidding phase
        phase = getattr(state, "phase", "playing")
        if phase == "bidding":
            return await self._build_bidding_async(
                state=state,
                legal_actions=legal_actions,
                engine=engine,
                player_id=player_id,
                db=db,
                session_id=session_id,
                version=version,
            )

        # Playing phase
        return await self._build_playing_async(
            state=state,
            legal_actions=legal_actions,
            engine=engine,
            player_id=player_id,
            game_type=game_type,
            db=db,
            session_id=session_id,
            version=version,
            tool_analysis=tool_analysis,
        )

    async def _build_playing_async(
        self,
        state: GameState,
        legal_actions: list[GameAction],
        engine: GameEngine,
        player_id: str,
        game_type: str,
        db: aiosqlite.Connection | None,
        session_id: str | None,
        version: str = "v1",
        tool_analysis: str | None = None,
    ) -> list[dict[str, str]]:
        """Build playing phase prompt with template from registry."""
        # Load rules
        if game_type not in _rules_cache:
            _rules_cache[game_type] = _load_rules(game_type)
        rules = _rules_cache[game_type]
        game_type_cn = GAME_TYPE_CN.get(game_type, game_type)

        # Get format instructions from LangChain parser
        format_instructions = _action_parser.get_format_instructions()

        # Get template from registry (with DB support)
        template_key = f"{game_type}_playing"
        try:
            template_content = await self._registry.get_template(
                template_key=template_key,
                db=db,
                version=version,
                session_id=session_id,
            )
        except ValueError:
            # Fallback to legacy template
            template_content = SYSTEM_TEMPLATE

        # Format system message
        system_msg = template_content.format(
            game_type_cn=game_type_cn,
            rules=rules,
            format_instructions=format_instructions,
        )

        state_desc = engine.format_for_prompt(state, player_id)
        actions_str = self._format_legal_actions(legal_actions)

        user_parts: list[str] = [
            state_desc,
            "",
        ]
        if tool_analysis:
            user_parts.extend(["## AI分析", tool_analysis, ""])
        user_parts.extend([
            "## 可选动作",
            actions_str,
            "",
            "请决策：",
        ])

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

    async def _build_bidding_async(
        self,
        state: GameState,
        legal_actions: list[GameAction],
        engine: GameEngine,
        player_id: str,
        db: aiosqlite.Connection | None,
        session_id: str | None,
        version: str = "v1",
    ) -> list[dict[str, str]]:
        """Build bidding phase prompt with template from registry."""
        # Get format instructions from LangChain parser
        format_instructions = _bid_parser.get_format_instructions()

        # Get template from registry (with DB support)
        template_key = "doudizhu_bidding"
        try:
            template_content = await self._registry.get_template(
                template_key=template_key,
                db=db,
                version=version,
                session_id=session_id,
            )
        except ValueError:
            # Fallback to legacy template
            template_content = BIDDING_SYSTEM_TEMPLATE

        system_msg = template_content.format(
            format_instructions=format_instructions,
        )
        state_desc = engine.format_for_prompt(state, player_id)
        actions_str = self._format_legal_actions(legal_actions)

        user_parts = [
            "## 当前叫地主情况",
            state_desc,
            "",
            "## 可选动作",
            actions_str,
            "",
            "请分析手牌强度并决定叫分：",
        ]

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

    def build(
        self,
        state: GameState,
        legal_actions: list[GameAction],
        engine: GameEngine,
        player_id: str,
        model_name: str | None = None,
        tool_analysis: str | None = None,
    ) -> list[dict[str, str]]:
        """Build prompt synchronously (without database/A/B testing support).

        For full features, use build_async() instead.

        Args:
            state: Current game state
            legal_actions: List of legal actions
            engine: Game engine instance
            player_id: ID of the player making the decision
            model_name: Optional model name to select appropriate template version
            tool_analysis: Optional pre-formatted tool analysis text to inject
        """
        game_type = state.game_type
        version = self._select_version_for_model(model_name)

        # Check if in bidding phase
        phase = getattr(state, "phase", "playing")
        if phase == "bidding":
            return self._build_bidding(state, legal_actions, engine, player_id, version)

        # Playing phase
        if game_type not in _rules_cache:
            _rules_cache[game_type] = _load_rules(game_type)
        rules = _rules_cache[game_type]
        game_type_cn = GAME_TYPE_CN.get(game_type, game_type)

        # Get format instructions from LangChain parser
        format_instructions = _action_parser.get_format_instructions()

        # Try to get template from registry (without DB)
        template_key = f"{game_type}_playing"
        try:
            # Use sync approach - get from defaults
            import asyncio

            template_content = asyncio.get_event_loop().run_until_complete(
                self._registry.get_template(
                    template_key=template_key, db=None, version=version
                )
            )
        except Exception:
            template_content = SYSTEM_TEMPLATE

        system_msg = template_content.format(
            game_type_cn=game_type_cn,
            rules=rules,
            format_instructions=format_instructions,
        )

        state_desc = engine.format_for_prompt(state, player_id)
        actions_str = self._format_legal_actions(legal_actions)

        user_parts: list[str] = [
            state_desc,
            "",
        ]
        if tool_analysis:
            user_parts.extend(["## AI分析", tool_analysis, ""])
        user_parts.extend([
            "## 可选动作",
            actions_str,
            "",
            "请决策：",
        ])

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

    def _build_bidding(
        self,
        state: GameState,
        legal_actions: list[GameAction],
        engine: GameEngine,
        player_id: str,
        version: str = "v1",
    ) -> list[dict[str, str]]:
        """Build bidding phase prompt (synchronous fallback)."""
        # Get format instructions from LangChain parser
        format_instructions = _bid_parser.get_format_instructions()

        # Try to get template from registry
        template_key = "doudizhu_bidding"
        try:
            import asyncio

            template_content = asyncio.get_event_loop().run_until_complete(
                self._registry.get_template(template_key=template_key, db=None, version=version)
            )
        except Exception:
            template_content = BIDDING_SYSTEM_TEMPLATE

        system_msg = template_content.format(
            format_instructions=format_instructions,
        )
        state_desc = engine.format_for_prompt(state, player_id)
        actions_str = self._format_legal_actions(legal_actions)

        user_parts = [
            "## 当前叫地主情况",
            state_desc,
            "",
            "## 可选动作",
            actions_str,
            "",
            "请分析手牌强度并决定叫分：",
        ]

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

    @staticmethod
    def format_tool_results(
        hand_analysis: HandAnalysis | None = None,
        win_probability: WinProbabilityResult | None = None,
    ) -> str | None:
        """Format tool analysis results into a Chinese text section for the prompt.

        Returns None if neither tool has results.
        """
        parts: list[str] = []
        if hand_analysis is not None:
            parts.append(
                f"**手牌分析**: 强度 {hand_analysis.strength_score:.0f}/100, "
                f"炸弹 {hand_analysis.bomb_count} 个"
                + (", 有火箭" if hand_analysis.rocket else "")
                + f", 顺子潜力 {hand_analysis.potential_chains} 个"
            )
            if hand_analysis.recommendations:
                parts.append(f"**建议**: {'; '.join(hand_analysis.recommendations)}")

        if win_probability is not None:
            pct = win_probability.probability * 100
            parts.append(
                f"**胜率估算**: {pct:.0f}% (置信度: {win_probability.confidence})"
            )
            if win_probability.reasoning:
                parts.append(f"**分析**: {win_probability.reasoning}")

        return "\n".join(parts) if parts else None

    @staticmethod
    def _format_legal_actions(actions: list[GameAction]) -> str:
        if not actions:
            return "无可选动作"

        # Sort by action type priority (descending), then by card power
        def sort_key(a: GameAction) -> tuple[int, int]:
            priority = ACTION_PRIORITY.get(str(a.action_type), 0)
            # For BID actions, sort by bid value descending
            if a.action_type == ActionType.BID and a.target:
                return (priority, int(a.target))
            # For card actions, sort by first card power descending
            card_power = max((ord(c[0]) for c in a.cards), default=0) if a.cards else 0
            return (priority, card_power)

        sorted_actions = sorted(actions, key=sort_key, reverse=True)

        lines: list[str] = []
        seen: set[str] = set()
        for a in sorted_actions:
            cards_str = " ".join(sort_cards(a.cards)) if a.cards else ""
            key = f"{a.action_type}:{cards_str}:{getattr(a, 'target', '')}"
            if key in seen:
                continue
            seen.add(key)

            if a.action_type == ActionType.PASS:
                lines.append(f"{len(lines) + 1}. PASS（不出）")
            elif a.action_type == ActionType.BID_PASS:
                lines.append(f"{len(lines) + 1}. BID_PASS（不叫）")
            elif a.action_type == ActionType.BID:
                lines.append(f"{len(lines) + 1}. BID {a.target}分（叫{a.target}分）")
            else:
                lines.append(f"{len(lines) + 1}. {a.action_type}: [{cards_str}]")

            if len(lines) >= 80:
                remaining = len(sorted_actions) - len(seen)
                if remaining > 0:
                    lines.append(f"...还有 {remaining} 个可选动作未列出")
                break

        return "\n".join(lines)
