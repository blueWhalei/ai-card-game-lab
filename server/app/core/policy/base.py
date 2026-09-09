"""Policy layer: how an action is chosen.

``LLMClient`` is transport (who produces tokens); a ``Policy`` is the decision
procedure (how those tokens, tools, or rules become a move). A policy sees an
``Observation`` and normalized ``LegalAction`` ids only -- never a ``GameState``,
so it cannot read hidden information -- and reports progress as an event stream.

The event stream is the single interface between this layer and the service
layer: a policy knows nothing about WebSocket broadcasting, traces, or decision
point persistence. Services consume the events and decide what to do with them.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias

from app.core.engine.base import ActionId, LegalAction
from app.core.engine.observation import Observation
from app.utils.exceptions import InvalidActionError


@dataclass(frozen=True)
class ThinkingDelta:
    """Incremental reasoning text, forwarded to the observer UI.

    ``channel`` separates a model's chain-of-thought from its answer; the
    observer renders them differently.
    """

    text: str
    channel: Literal["reasoning", "content"] = "content"
    type: Literal["thinking_delta"] = "thinking_delta"


@dataclass(frozen=True)
class ToolCall:
    """A policy asked the engine to run one of its declared tools."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    type: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool call, JSON-safe."""

    name: str
    result: dict[str, Any] = field(default_factory=dict)
    type: Literal["tool_result"] = "tool_result"


@dataclass(frozen=True)
class LlmRequest:
    """The messages sent to a model.

    The observer shows the exact prompt behind a move, and a trace stores it, so
    what was sent has to leave the policy. Policies that never call a model
    simply never emit this.
    """

    messages: list[dict[str, str]] = field(default_factory=list)
    type: Literal["llm_request"] = "llm_request"


@dataclass(frozen=True)
class LlmUsage:
    """Token accounting for one model call."""

    usage: dict[str, int | None] = field(default_factory=dict)
    model: str | None = None
    type: Literal["llm_usage"] = "llm_usage"


@dataclass(frozen=True)
class ActionChosen:
    """Terminal event: the decision. ``action_id`` must be currently legal."""

    action_id: ActionId
    thinking: str = ""
    raw_response: str = ""
    parse_fallback: bool = False
    type: Literal["action_chosen"] = "action_chosen"


PolicyEvent: TypeAlias = (
    ThinkingDelta | ToolCall | ToolResult | LlmRequest | LlmUsage | ActionChosen
)


@dataclass(frozen=True)
class Budget:
    """How much compute one decision may spend.

    Model parameters (temperature, max_tokens) are policy configuration, not
    budget: they describe *how* the model answers, not how much work is allowed.
    """

    max_llm_calls: int = 1
    max_tool_calls: int = 0
    timeout_s: float | None = None


class EngineAdvisor(Protocol):
    """The slice of the engine a policy is allowed to use.

    ``GameEngine`` satisfies this structurally. Narrowing it here is what keeps
    ``GameState`` -- and therefore hidden information -- out of reach.
    """

    def tool_names(self, phase: str | None = None) -> list[str]: ...

    def run_tool(
        self, name: str, observation: Observation, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    def suggest_action(
        self, observation: Observation, legal_actions: list[LegalAction]
    ) -> ActionId | None: ...


class PromptSource(Protocol):
    """Resolves the system message for one decision.

    Template lookup means a database read and reading the engine's rules file --
    infrastructure a policy must not own. The service layer implements this and
    hands over rendered text; the policy supplies ``format_instructions`` because
    the output protocol is its concern.
    """

    async def system_message(
        self,
        *,
        phase: str,
        model_name: str | None,
        format_instructions: str,
    ) -> str: ...


@dataclass(frozen=True)
class PolicyContext:
    """External dependencies handed to a policy.

    Policies never read settings, open connections, or use module-level
    randomness; everything comes through here so a decision is reproducible.
    """

    advisor: EngineAdvisor
    rng: random.Random
    session_id: str | None = None
    prompts: PromptSource | None = None
    # Optional EV scorer for SearchAugmentedPolicy (Observation-only; no GameState).
    score_actions: Callable[
        [Observation, list[LegalAction], list[ActionId]],
        dict[ActionId, float],
    ] | None = None
    # Per-experiment opponent notes (injected into LLM prompts when set).
    memory_notes: str | None = None


class ActionSelector(Protocol):
    """Synchronous action choice.

    ``Policy`` is async because an LLM call is I/O. Rollouts are pure CPU work and
    must not be dragged into the event loop, so the evaluator consumes selectors
    instead. Baseline policies implement both: the logic lives in ``choose`` and
    ``decide`` wraps it, so there is only ever one implementation.
    """

    def choose(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
    ) -> ActionId: ...


class Policy(ABC):
    """Chooses one legal action and reports progress as events."""

    kind: str = "policy"

    @abstractmethod
    def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]:
        """Stream the decision process.

        The last event must be ``ActionChosen`` carrying an id from
        ``legal_actions``. Implementations may yield any number of other events
        before it.
        """

    async def decide_action(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> ActionChosen:
        """Drain the stream and return only the decision.

        Used where the reasoning trace is irrelevant, e.g. evaluator rollouts.
        """
        chosen: ActionChosen | None = None
        async for event in self.decide(observation, legal_actions, budget, ctx):
            if isinstance(event, ActionChosen):
                chosen = event
        if chosen is None:
            raise InvalidActionError(self.kind, "Policy finished without choosing an action")
        return chosen
