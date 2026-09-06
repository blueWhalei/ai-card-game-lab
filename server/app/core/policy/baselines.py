"""Non-LLM baseline policies.

Without these, a win rate has no reference point and CI cannot run a real game
without spending API budget. All three are game-agnostic: any game knowledge
comes from the engine through ``PolicyContext.advisor``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.engine.base import LegalAction
from app.core.engine.observation import Observation
from app.core.policy.base import (
    ActionChosen,
    Budget,
    Policy,
    PolicyContext,
    PolicyEvent,
)
from app.utils.exceptions import InvalidActionError


def _require_actions(kind: str, legal_actions: list[LegalAction]) -> None:
    if not legal_actions:
        raise InvalidActionError(kind, "No legal actions to choose from")


class RandomPolicy(Policy):
    """Uniform choice among legal actions -- the evaluation floor."""

    kind = "random"

    async def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]:
        del observation, budget
        _require_actions(self.kind, legal_actions)
        chosen = ctx.rng.choice(legal_actions)
        yield ActionChosen(action_id=chosen.id, thinking=f"random: {chosen.label}")


class FirstActionPolicy(Policy):
    """Always take the engine's first presented action.

    Deterministic, so it is the policy to reach for when a test needs a stable
    opponent. In Doudizhu the engine presents the strongest card type first.
    """

    kind = "first"

    async def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]:
        del observation, budget, ctx
        _require_actions(self.kind, legal_actions)
        chosen = legal_actions[0]
        yield ActionChosen(action_id=chosen.id, thinking=f"first: {chosen.label}")


class HeuristicPolicy(Policy):
    """Delegate to the engine's house heuristic, falling back to random.

    This is the meaningful non-LLM opponent: strong enough to make a win rate
    interpretable, and cheap enough to use as a rollout opponent.
    """

    kind = "heuristic"

    async def decide(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        budget: Budget,
        ctx: PolicyContext,
    ) -> AsyncIterator[PolicyEvent]:
        del budget
        _require_actions(self.kind, legal_actions)

        suggestion = ctx.advisor.suggest_action(observation, legal_actions)
        by_id = {action.id: action for action in legal_actions}
        if suggestion is not None and suggestion in by_id:
            chosen = by_id[suggestion]
            yield ActionChosen(
                action_id=chosen.id, thinking=f"heuristic: {chosen.label}"
            )
            return

        chosen = ctx.rng.choice(legal_actions)
        yield ActionChosen(
            action_id=chosen.id, thinking=f"heuristic (no suggestion): {chosen.label}"
        )
