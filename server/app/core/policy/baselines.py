"""Non-LLM baseline policies.

Without these, a win rate has no reference point and CI cannot run a real game
without spending API budget. All three are game-agnostic: any game knowledge
comes from the engine through ``PolicyContext.advisor``.

Each one implements the decision once, in ``choose``; ``decide`` only wraps it as
a single-event stream. The rollout evaluator uses ``choose`` directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.engine.base import ActionId, LegalAction
from app.core.engine.observation import Observation
from app.core.policy.base import (
    ActionChosen,
    Budget,
    Policy,
    PolicyContext,
    PolicyEvent,
)
from app.utils.exceptions import InvalidActionError


class BaselinePolicy(Policy):
    """Shared plumbing: ``decide`` is ``choose`` wrapped as one event."""

    def choose(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
    ) -> ActionId:
        raise NotImplementedError

    async def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]:
        del budget
        chosen = self.choose(observation, legal_actions, ctx)
        yield ActionChosen(action_id=chosen, thinking=f"{self.kind}: {chosen}")

    def _require_actions(self, legal_actions: list[LegalAction]) -> None:
        if not legal_actions:
            raise InvalidActionError(self.kind, "No legal actions to choose from")


class RandomPolicy(BaselinePolicy):
    """Uniform choice among legal actions -- the evaluation floor."""

    kind = "random"

    def choose(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
    ) -> ActionId:
        del observation
        self._require_actions(legal_actions)
        return ctx.rng.choice(legal_actions).id


class FirstActionPolicy(BaselinePolicy):
    """Always take the engine's first presented action.

    Deterministic, so it is the policy to reach for when a test needs a stable
    opponent. In Doudizhu the engine presents the strongest card type first.
    """

    kind = "first"

    def choose(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
    ) -> ActionId:
        del observation, ctx
        self._require_actions(legal_actions)
        return legal_actions[0].id


class HeuristicPolicy(BaselinePolicy):
    """Delegate to the engine's house heuristic, falling back to random.

    This is the meaningful non-LLM opponent: strong enough to make a win rate
    interpretable, and cheap enough to use as a rollout opponent.
    """

    kind = "heuristic"

    def choose(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        ctx: PolicyContext,
    ) -> ActionId:
        self._require_actions(legal_actions)
        suggestion = ctx.advisor.suggest_action(observation, legal_actions)
        if suggestion is not None and any(a.id == suggestion for a in legal_actions):
            return suggestion
        return ctx.rng.choice(legal_actions).id
