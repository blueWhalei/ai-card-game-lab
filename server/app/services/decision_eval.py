"""Scores a live decision with the rollout evaluator.

Sits between the game loop and ``core/eval``: the game loop has the live state,
the evaluator wants an ``Observation`` plus normalized legal actions.

Why here and not after the game: a stored decision point keeps card lists and
action dicts, not ``ActionId`` values or the public information
``sample_hidden_state`` needs to rebuild a world. At decision time all of that is
already in hand.
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.engine.base import GameAction, GameEngine, GameState
from app.core.eval.rollout import EvaluatorParams, EvLoss, RolloutEvaluator
from app.core.policy.baselines import HeuristicPolicy

logger = structlog.get_logger()


class DecisionEvaluator:
    """Computes EV loss for moves as they happen, or returns ``None``.

    Never raises: EV loss is an analysis signal, and a game must not fail because
    a simulation did. Callers store ``None`` as "not evaluated", which downstream
    keeps distinct from a loss of 0.0 ("gave up nothing").
    """

    def __init__(self, params: EvaluatorParams | None = None) -> None:
        self._params = params or EvaluatorParams()
        self._opponent = HeuristicPolicy()
        self._evaluators: dict[str, RolloutEvaluator] = {}

    @property
    def params(self) -> EvaluatorParams:
        return self._params

    def supports(self, engine: GameEngine) -> bool:
        return engine.capability.supports_hidden_state_sampling

    async def score(
        self,
        engine: GameEngine,
        state: GameState,
        player_id: str,
        chosen_action: GameAction,
    ) -> EvLoss | None:
        """EV loss for ``chosen_action``, or ``None`` when it cannot be computed."""
        if not self.supports(engine):
            return None
        try:
            return await asyncio.to_thread(
                self._score_sync, engine, state, player_id, chosen_action
            )
        except Exception as error:
            # Broad on purpose: a simulation must never take a game down with it.
            logger.warning(
                "ev_loss_failed",
                game_type=engine.game_type,
                player_id=player_id,
                error=str(error),
            )
            return None

    def _score_sync(
        self,
        engine: GameEngine,
        state: GameState,
        player_id: str,
        chosen_action: GameAction,
    ) -> EvLoss:
        evaluator = self._evaluator_for(engine)
        observation = engine.observe(state, player_id)
        legal_actions = engine.legal_actions(state, player_id)
        return evaluator.ev_loss(
            observation, legal_actions, engine.action_id(chosen_action)
        )

    def _evaluator_for(self, engine: GameEngine) -> RolloutEvaluator:
        cached = self._evaluators.get(engine.game_type)
        if cached is None:
            cached = RolloutEvaluator(engine, self._opponent, self._params)
            self._evaluators[engine.game_type] = cached
        return cached
