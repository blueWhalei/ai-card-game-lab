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
from app.core.policy.llm import LLMPolicy
from app.core.policy.registry import PolicyRegistry

__all__ = [
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
    "Policy",
    "PolicyContext",
    "PolicyEvent",
    "PolicyRegistry",
    "PromptSource",
    "RandomPolicy",
    "ThinkingDelta",
    "ToolCall",
    "ToolResult",
]


def get_baseline_policy_registry() -> PolicyRegistry:
    """Registry preloaded with the non-LLM baselines."""
    registry = PolicyRegistry()
    registry.register("random", lambda _params: RandomPolicy())
    registry.register("first", lambda _params: FirstActionPolicy())
    registry.register("heuristic", lambda _params: HeuristicPolicy())
    return registry
