"""Rollout evaluator: what was that move worth?

Turns an outcome-only signal into a per-decision one. ``quality_score`` says who
won the game; this says how much value the chosen move gave up compared with the
best move considered. That is the difference between one sample per game and one
sample per decision.

Pure CPU work, so this module is synchronous by design -- callers in the service
layer wrap it in ``asyncio.to_thread()``.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

from app.core.engine.base import ActionId, GameEngine, GameState, LegalAction
from app.core.engine.observation import Observation
from app.core.policy.base import ActionSelector, PolicyContext
from app.utils.exceptions import InvalidActionError


@dataclass(frozen=True)
class EvaluatorParams:
    """Every knob that changes an EV number.

    Stored alongside results so two EV losses are only ever compared when they
    were produced the same way.
    """

    determinizations: int = 4
    rollouts_per_world: int = 1
    max_candidates: int = 8
    max_steps: int = 400
    opponent_kind: str = "heuristic"
    # When opponent_kind is ``self`` and the seat is LLM, fall back to this baseline.
    self_proxy: str = "heuristic"
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "determinizations": self.determinizations,
            "rollouts_per_world": self.rollouts_per_world,
            "max_candidates": self.max_candidates,
            "max_steps": self.max_steps,
            "opponent_kind": self.opponent_kind,
            "self_proxy": self.self_proxy,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class EvLoss:
    """How much value a decision gave up.

    ``best_action_id`` is the best of the **evaluated candidates**, not of every
    legal action -- see ``candidates_evaluated``. Reporting both keeps the number
    honest when ``max_candidates`` truncated the search.
    """

    chosen_action_id: ActionId
    chosen_value: float
    best_action_id: ActionId
    best_value: float
    loss: float
    candidates_evaluated: int
    legal_action_count: int
    values: dict[ActionId, float] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def truncated(self) -> bool:
        """Whether some legal actions went unevaluated."""
        return self.candidates_evaluated < self.legal_action_count


class RolloutEvaluator:
    """Scores candidate actions by simulating the rest of the game.

    Imperfect-information games need determinization first: sample worlds that
    match what the player can see, then play each candidate out in those worlds.
    The same worlds are reused for every candidate (common random numbers),
    because the difference between candidates is the signal and shared randomness
    is what stops variance from swamping it.
    """

    def __init__(
        self,
        engine: GameEngine,
        opponent: ActionSelector,
        params: EvaluatorParams | None = None,
    ) -> None:
        if not engine.capability.supports_hidden_state_sampling:
            raise InvalidActionError(
                engine.game_type,
                "Rollout evaluation needs an engine that can sample hidden state",
            )
        self._engine = engine
        self._opponent = opponent
        self._params = params or EvaluatorParams()

    @property
    def params(self) -> EvaluatorParams:
        return self._params

    def action_values(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        *,
        must_include: ActionId | None = None,
    ) -> dict[ActionId, float]:
        """Expected payoff for the viewer per candidate action."""
        candidates = self._select_candidates(legal_actions, must_include)
        if not candidates:
            raise InvalidActionError("action_values", "No candidate actions to evaluate")

        totals: dict[ActionId, float] = dict.fromkeys(
            (candidate.id for candidate in candidates), 0.0
        )
        rollouts = 0

        for world_index in range(self._params.determinizations):
            world = self._engine.sample_hidden_state(observation, self._rng("world", world_index))
            for repeat in range(self._params.rollouts_per_world):
                for candidate in candidates:
                    # Same rng stream for every candidate in this world: common
                    # random numbers, so the spread between candidates is signal
                    # rather than luck.
                    totals[candidate.id] += self._playout(
                        world,
                        observation.player_id,
                        candidate.id,
                        self._rng("rollout", world_index, repeat),
                    )
            rollouts += self._params.rollouts_per_world

        return {action_id: total / rollouts for action_id, total in totals.items()}

    def ev_loss(
        self,
        observation: Observation,
        legal_actions: list[LegalAction],
        chosen_action_id: ActionId,
    ) -> EvLoss:
        """Value given up by ``chosen_action_id``. Never negative."""
        if not any(action.id == chosen_action_id for action in legal_actions):
            raise InvalidActionError(chosen_action_id, "Chosen action is not legal here")

        values = self.action_values(observation, legal_actions, must_include=chosen_action_id)
        best_action_id = max(values, key=lambda action_id: values[action_id])

        return EvLoss(
            chosen_action_id=chosen_action_id,
            chosen_value=values[chosen_action_id],
            best_action_id=best_action_id,
            best_value=values[best_action_id],
            loss=values[best_action_id] - values[chosen_action_id],
            candidates_evaluated=len(values),
            legal_action_count=len(legal_actions),
            values=values,
            params=self._params.to_dict(),
        )

    def _select_candidates(
        self, legal_actions: list[LegalAction], must_include: ActionId | None
    ) -> list[LegalAction]:
        """Engine order, truncated -- but never dropping the action under review."""
        limit = max(1, self._params.max_candidates)
        selected = legal_actions[:limit]
        if must_include is None or any(a.id == must_include for a in selected):
            return selected

        forced = next(a for a in legal_actions if a.id == must_include)
        return [forced, *selected[: limit - 1]]

    def _playout(
        self,
        world: GameState,
        viewer_id: str,
        first_action_id: ActionId,
        rng: random.Random,
    ) -> float:
        """Apply one candidate, then let the reference selector finish the game."""
        engine = self._engine
        state = engine.apply_action(world, engine.resolve_action(world, viewer_id, first_action_id))
        ctx = PolicyContext(advisor=engine, rng=rng, session_id=None)

        for _ in range(self._params.max_steps):
            if engine.is_terminal(state):
                return engine.terminal_rewards(state)[viewer_id]
            player_id = engine.get_current_player(state)
            legal = engine.legal_actions(state, player_id)
            if not legal:
                break
            action_id = self._opponent.choose(engine.observe(state, player_id), legal, ctx)
            state = engine.apply_action(state, engine.resolve_action(state, player_id, action_id))

        # Scoring an unfinished game would invent signal (0.0 is a real loss
        # payoff), so refuse instead of guessing.
        raise InvalidActionError(
            "rollout",
            f"Game did not finish within {self._params.max_steps} steps",
        )

    def _rng(self, *parts: object) -> random.Random:
        """Deterministic across processes -- ``hash()`` of a str is not."""
        payload = "|".join(str(part) for part in (self._params.seed, *parts))
        digest = hashlib.blake2b(payload.encode(), digest_size=8).digest()
        return random.Random(int.from_bytes(digest, "big"))
