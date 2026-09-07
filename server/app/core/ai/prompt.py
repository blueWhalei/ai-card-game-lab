"""Prompt construction for LLM-based game agents.

``PromptBuilder`` owns the half of a prompt that needs infrastructure: which
template version applies, what the stored template says, and what the engine's
rules file contains. The user message -- board state, tool output, the menu of
legal actions -- is assembled by ``LLMPolicy`` from an ``Observation``, because
that half needs no database and no engine.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.ai.prompts.registry import PromptTemplateRegistry

if TYPE_CHECKING:
    import aiosqlite

    from app.core.engine.base import GameEngine

# ── Reasoning model detection ──────────────────────────────────────────────────
# Models that output chain-of-thought reasoning before the final answer
REASONING_MODEL_PATTERNS = [
    r"deepseek-v4-pro",
    r"deepseek-reasoner",
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

DEFAULT_TEMPLATE_VERSION = "v3"
REASONING_TEMPLATE_VERSION = "v3_reasoning"


def is_reasoning_model(model_name: str | None) -> bool:
    """Check if the model is a reasoning/thinking model.

    Reasoning models output chain-of-thought before the final answer,
    and require different prompt templates.
    """
    if not model_name:
        return False
    model_lower = model_name.lower()
    return any(re.search(pattern, model_lower) for pattern in REASONING_MODEL_PATTERNS)


# Built-in templates when a stored template is missing. Both defer the output
# contract to {format_instructions} -- restating it here is how a template ends up
# contradicting the protocol it is supposed to serve.
SYSTEM_TEMPLATE = """\
你是{game_type_cn} AI 玩家。你的玩家ID会在每轮提示中明确标注。

## 核心规则
{rules}

{format_instructions}
"""

BIDDING_SYSTEM_TEMPLATE = """\
你是斗地主 AI 玩家，正在进行叫地主阶段。

## 叫地主规则
- 可叫1/2/3分或选择不叫，叫分必须高于当前最高
- 叫3分立即成为地主（获得3张底牌，共20张）
- 三人都不叫则重新发牌

## 手牌评估
| 条件 | 叫分 |
|------|------|
| 有炸弹/王炸 或 ≥2张2 | 3分 |
| 有1张2 + 牌型好 | 2分 |
| 牌型一般但有大牌 | 1分 |
| 牌散且无大牌 | 不叫 |

{format_instructions}
"""


def _load_rules(game_type: str, rules_ref: str | None = None) -> str:
    """Load game rules from capability.rules_ref or docs fallback."""
    candidates: list[Path] = []
    repo_root = Path(__file__).parents[4]
    if rules_ref:
        ref_path = Path(rules_ref)
        candidates.append(ref_path if ref_path.is_absolute() else repo_root / rules_ref)
    # Default Dou Dizhu rules file when rules_ref is omitted
    if game_type == "doudizhu":
        candidates.append(repo_root / "docs" / "欢乐斗地主经典玩法规则.md")
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
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

# Global registry instance (initialized with defaults)
_registry = PromptTemplateRegistry()


def get_prompt_registry() -> PromptTemplateRegistry:
    """Get the global prompt template registry."""
    return _registry


class PromptBuilder:
    """Resolves the system message for one decision.

    Features:
    - Version-controlled prompt templates via Registry
    - A/B testing support
    - Automatic reasoning model detection
    """

    def __init__(
        self,
        registry: PromptTemplateRegistry | None = None,
        default_version: str = DEFAULT_TEMPLATE_VERSION,
    ) -> None:
        self._registry = registry or _registry
        self._default_version = default_version

    def _select_version_for_model(self, model_name: str | None) -> str:
        """Pick the template version for a model.

        Reasoning models get a variant that caps how long they think before
        answering; everything else gets the configured default.
        """
        if is_reasoning_model(model_name):
            return REASONING_TEMPLATE_VERSION
        return self._default_version

    @staticmethod
    def _template_key_for(engine: GameEngine, phase: str) -> str:
        keys = engine.capability.prompt_keys
        if phase in keys:
            return keys[phase]
        if "playing" in keys:
            return keys["playing"]
        return f"{engine.game_type}_{phase}"

    @staticmethod
    def _rules_for(engine: GameEngine) -> str:
        game_type = engine.game_type
        if game_type not in _rules_cache:
            _rules_cache[game_type] = _load_rules(game_type, engine.capability.rules_ref)
        return _rules_cache[game_type]

    async def system_message(
        self,
        *,
        engine: GameEngine,
        phase: str,
        format_instructions: str,
        model_name: str | None = None,
        session_id: str | None = None,
        db: aiosqlite.Connection | None = None,
    ) -> str:
        """Render the system message for one decision.

        This is the half of prompt building a policy cannot do for itself: it
        needs the template registry, the A/B assignment, and the engine's rules
        file. The user message is assembled by the caller from the observation.
        """
        template_key = self._template_key_for(engine, phase)
        try:
            template_content = await self._registry.get_template(
                template_key=template_key,
                db=db,
                version=self._select_version_for_model(model_name),
                session_id=session_id,
            )
        except ValueError:
            template_content = BIDDING_SYSTEM_TEMPLATE if phase == "bidding" else SYSTEM_TEMPLATE

        return template_content.format(
            game_type_cn=GAME_TYPE_CN.get(engine.game_type, engine.game_type),
            rules=self._rules_for(engine),
            format_instructions=format_instructions,
        )
