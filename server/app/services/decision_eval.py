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
from typing import Any

import structlog

from app.core.engine.base import GameAction, GameEngine, GameState
from app.core.eval.rollout import EvaluatorParams, EvLoss, RolloutEvaluator
from app.core.policy import ActionSelector, HeuristicPolicy, get_baseline_policy_registry
from app.core.policy.baselines import BaselinePolicy
from app.utils.exceptions import InvalidActionError

logger = structlog.get_logger()


def resolve_opponent(kind: str) -> ActionSelector:
    """Map ``EvaluatorParams.opponent_kind`` to a baseline policy."""
    try:
        policy = get_baseline_policy_registry().create(kind)
    except InvalidActionError:
        logger.warning("unknown_opponent_kind", opponent_kind=kind)
        return HeuristicPolicy()
    if isinstance(policy, BaselinePolicy):
        return policy
    logger.warning("opponent_kind_not_baseline", opponent_kind=kind)
    return HeuristicPolicy()


def _params_cache_key(params: EvaluatorParams) -> tuple[Any, ...]:
    return tuple(sorted(params.to_dict().items()))


class DecisionEvaluator:
    """Computes EV loss for moves as they happen, or returns ``None``.

    Never raises: EV loss is an analysis signal, and a game must not fail because
    a simulation did. Callers store ``None`` as "not evaluated", which downstream
    keeps distinct from a loss of 0.0 ("gave up nothing").

    Default knobs come from Settings; per-call ``params`` (from an experiment
    protocol) override without mutating the default instance.
    """

    def __init__(self, params: EvaluatorParams | None = None) -> None:
        self._params = params or EvaluatorParams()
        self._opponent = resolve_opponent(self._params.opponent_kind)
        self._evaluators: dict[tuple[Any, ...], RolloutEvaluator] = {}

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
        *,
        params: EvaluatorParams | None = None,
    ) -> EvLoss | None:
        """EV loss for ``chosen_action``, or ``None`` when it cannot be computed."""
        if not self.supports(engine):
            return None
        effective = params or self._params
        try:
            return await asyncio.to_thread(
                self._score_sync, engine, state, player_id, chosen_action, effective
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
        params: EvaluatorParams,
    ) -> EvLoss:
        evaluator = self._evaluator_for(engine, params)
        observation = engine.observe(state, player_id)
        legal_actions = engine.legal_actions(state, player_id)
        return evaluator.ev_loss(
            observation, legal_actions, engine.action_id(chosen_action)
        )

    def _evaluator_for(
        self, engine: GameEngine, params: EvaluatorParams
    ) -> RolloutEvaluator:
        key = (engine.game_type, *_params_cache_key(params))
        cached = self._evaluators.get(key)
        if cached is None:
            opponent = (
                self._opponent
                if params.opponent_kind == self._params.opponent_kind
                else resolve_opponent(params.opponent_kind)
            )
            cached = RolloutEvaluator(engine, opponent, params)
            self._evaluators[key] = cached
        return cached
