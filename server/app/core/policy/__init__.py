"""Policy package: decision procedures that turn an observation into an action."""

from app.core.policy.base import (
    ActionChosen,
    Budget,
    EngineAdvisor,
    LlmUsage,
    Policy,
    PolicyContext,
    PolicyEvent,
    ThinkingDelta,
    ToolCall,
    ToolResult,
)
from app.core.policy.baselines import FirstActionPolicy, HeuristicPolicy, RandomPolicy
from app.core.policy.registry import PolicyRegistry

__all__ = [
    "ActionChosen",
    "Budget",
    "EngineAdvisor",
    "FirstActionPolicy",
    "HeuristicPolicy",
    "LlmUsage",
    "Policy",
    "PolicyContext",
    "PolicyEvent",
    "PolicyRegistry",
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
