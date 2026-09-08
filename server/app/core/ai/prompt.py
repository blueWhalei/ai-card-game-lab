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

from app.core.ai.prompts.registry import (
    DEFAULT_TEMPLATE_VERSION,
    REASONING_TEMPLATE_VERSION,
    PromptTemplateRegistry,
)
from app.core.engine.prompt_defaults import SYSTEM_TEMPLATE

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


def is_reasoning_model(model_name: str | None) -> bool:
    """Check if the model is a reasoning/thinking model.

    Reasoning models output chain-of-thought before the final answer,
    and require different prompt templates.
    """
    if not model_name:
        return False
    model_lower = model_name.lower()
    return any(re.search(pattern, model_lower) for pattern in REASONING_MODEL_PATTERNS)


_MISSING_RULES = "（未配置 rules_ref，或规则文件不存在。）"


def _load_rules(rules_ref: str | None) -> str:
    """Load game rules from capability.rules_ref only (no per-game hardcoding)."""
    if not rules_ref:
        return _MISSING_RULES
    repo_root = Path(__file__).parents[4]
    ref_path = Path(rules_ref)
    path = ref_path if ref_path.is_absolute() else repo_root / rules_ref
    if path.exists():
        return path.read_text(encoding="utf-8")
    return _MISSING_RULES


# Cache loaded rules by rules_ref (empty key = missing)
_rules_cache: dict[str, str] = {}

# Global registry instance (initialized with defaults)
_registry = PromptTemplateRegistry()


def get_prompt_registry() -> PromptTemplateRegistry:
    """Get the global prompt template registry."""
    return _registry


class PromptBuilder:
    """Resolves the system message for one decision.

    Picks the template version from the model (reasoning models get a variant),
    reads the stored template, and fills in the engine's rules.
    """

    def __init__(
        self,
        registry: PromptTemplateRegistry | None = None,
        default_version: str = DEFAULT_TEMPLATE_VERSION,
    ) -> None:
        self._registry = registry or _registry
        self._default_version = default_version

    def version_for(self, model_name: str | None) -> str:
        """Pick the template version for a model.

        Reasoning models get a variant that caps how long they think before
        answering; everything else gets the default. Public because a trace has to
        record the version a decision actually used, not a placeholder.
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
        rules_ref = engine.capability.rules_ref or ""
        cache_key = rules_ref or f"__missing__:{engine.game_type}"
        if cache_key not in _rules_cache:
            _rules_cache[cache_key] = _load_rules(engine.capability.rules_ref)
        return _rules_cache[cache_key]

    async def system_message(
        self,
        *,
        engine: GameEngine,
        phase: str,
        format_instructions: str,
        model_name: str | None = None,
        db: aiosqlite.Connection | None = None,
        frozen_content: str | None = None,
    ) -> str:
        """Render the system message for one decision.

        This is the half of prompt building a policy cannot do for itself: it
        needs the template registry and the engine's rules file. The user message
        is assembled by the caller from the observation.

        When *frozen_content* is set (experiment protocol snapshot), that body is
        used as-is — live DB edits and reasoning-model version switching do not
        apply.
        """
        if frozen_content is not None:
            template_content = frozen_content
        else:
            template_key = self._template_key_for(engine, phase)
            try:
                template_content = await self._registry.get_template(
                    template_key=template_key,
                    db=db,
                    version=self.version_for(model_name),
                )
            except ValueError:
                template_content = engine.default_system_template(phase)

        display = engine.capability.display_name or engine.game_type
        return template_content.format(
            game_type_cn=display,
            rules=self._rules_for(engine),
            format_instructions=format_instructions,
        )


__all__ = [
    "SYSTEM_TEMPLATE",
    "PromptBuilder",
    "get_prompt_registry",
    "is_reasoning_model",
]
