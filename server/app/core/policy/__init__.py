"""Policy package: decision procedures that turn an observation into an action."""

from app.core.policy.base import (
    ActionChosen,
    ActionSelector,
    Budget,
    EngineAdvisor,
    LlmRequest,
    LlmUsage,
    Policy,
    PolicyContext,
    PolicyEvent,
    PromptSource,
    ThinkingDelta,
    ToolCall,
    ToolResult,
)
from app.core.policy.baselines import (
    BaselinePolicy,
    FirstActionPolicy,
    HeuristicPolicy,
    RandomPolicy,
)
from app.core.policy.kinds import (
    BASELINE_POLICY_KINDS,
    LLM_POLICY_KINDS,
    PLAYER_POLICY_KINDS,
    PlayerPolicyKind,
    baseline_placeholder_model_config,
    is_baseline_policy_kind,
    is_llm_policy_kind,
    normalize_player_policy_kind,
)
from app.core.policy.llm import LLMPolicy
from app.core.policy.registry import PolicyRegistry
from app.core.policy.tool_loop import ToolLoopPolicy

__all__ = [
    "BASELINE_POLICY_KINDS",
    "LLM_POLICY_KINDS",
    "PLAYER_POLICY_KINDS",
    "ActionChosen",
    "ActionSelector",
    "BaselinePolicy",
    "Budget",
    "EngineAdvisor",
    "FirstActionPolicy",
    "HeuristicPolicy",
    "LLMPolicy",
    "LlmRequest",
    "LlmUsage",
    "PlayerPolicyKind",
    "Policy",
    "PolicyContext",
    "PolicyEvent",
    "PolicyRegistry",
    "PromptSource",
    "RandomPolicy",
    "ThinkingDelta",
    "ToolCall",
    "ToolLoopPolicy",
    "ToolResult",
    "baseline_placeholder_model_config",
    "is_baseline_policy_kind",
    "is_llm_policy_kind",
    "normalize_player_policy_kind",
]


def get_baseline_policy_registry() -> PolicyRegistry:
    """Registry preloaded with the non-LLM baselines."""
    registry = PolicyRegistry()
    registry.register("random", lambda _params: RandomPolicy())
    registry.register("first", lambda _params: FirstActionPolicy())
    registry.register("heuristic", lambda _params: HeuristicPolicy())
    return registry
