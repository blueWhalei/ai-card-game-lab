"""PettingZoo-style AEC environment wrapping a CardLab ``GameEngine``.

Duck-typed API (no ``pettingzoo`` dependency): ``reset`` / ``agent_iter`` /
``last`` / ``step``. The external learner acts only for ``learner_id`` via an
integer index into the current legal menu; other seats are driven by an injected
``ActionSelector`` (default: house heuristic).
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

from app.core.engine.base import GameAction, GameEngine, GameState, LegalAction
from app.core.policy.base import ActionSelector, PolicyContext
from app.core.policy.baselines import HeuristicPolicy
from app.utils.exceptions import InvalidActionError

ObsDict = dict[str, Any]
LastTuple = tuple[ObsDict, float, bool, bool, dict[str, Any]]


class CardLabAECEnv:
    """Single-learner AEC wrapper over a multi-player card engine."""

    def __init__(
        self,
        engine: GameEngine,
        player_ids: list[str],
        *,
        learner_id: str,
        opponent: ActionSelector | None = None,
        opponent_seed: int = 0,
    ) -> None:
        if learner_id not in player_ids:
            raise ValueError(f"learner_id {learner_id!r} not in player_ids {player_ids}")
        self._engine = engine
        self.agents: list[str] = list(player_ids)
        self.possible_agents: list[str] = list(player_ids)
        self._learner_id = learner_id
        self._opponent: ActionSelector = opponent or HeuristicPolicy()
        self._opponent_seed = opponent_seed

        self._state: GameState | None = None
        self._legal: list[LegalAction] = []
        self._pending_reward: float = 0.0
        self._terminated: bool = False
        self._opp_rng = random.Random(opponent_seed)

        self.agent_selection: str | None = None
        self.rewards: dict[str, float] = {pid: 0.0 for pid in self.agents}
        self.terminations: dict[str, bool] = {pid: False for pid in self.agents}
        self.truncations: dict[str, bool] = {pid: False for pid in self.agents}
        self.infos: dict[str, dict[str, Any]] = {pid: {} for pid in self.agents}

    def reset(self, seed: int | None = None) -> None:
        """Start a new game and advance until the learner must act (or terminal)."""
        init_kwargs: dict[str, Any] = {}
        if seed is not None:
            init_kwargs["seed"] = seed
        self._opp_rng = random.Random(
            self._opponent_seed if seed is None else (seed ^ self._opponent_seed)
        )
        self._state = self._engine.initialize(self.agents, **init_kwargs)
        self._pending_reward = 0.0
        self._terminated = False
        self._legal = []
        self.agent_selection = None
        self._clear_agent_dicts()
        self._advance_to_learner_or_end()
        self._sync_agent_dicts()

    def agent_iter(self, max_iter: int = 10_000) -> Iterator[str]:
        """Yield ``learner_id`` until the episode has been observed as terminated.

        Typical use::

            env.reset(seed=42)
            for _agent in env.agent_iter():
                obs, reward, term, trunc, info = env.last()
                if term or trunc:
                    break
                env.step(policy(obs))
        """
        if self._state is None:
            return
        for _ in range(max_iter):
            already_done = self._terminated
            yield self._learner_id
            if already_done:
                return

    def last(self) -> LastTuple:
        """Observation and outcome for the current ``agent_selection`` (learner)."""
        if self._state is None:
            raise RuntimeError("reset() must be called before last()")
        obs = self._observation_dict()
        info = {
            "legal_action_count": len(self._legal),
            "phase": getattr(self._state, "phase", ""),
            "round": int(getattr(self._state, "round", 0)),
            "learner_id": self._learner_id,
        }
        return (
            obs,
            float(self._pending_reward),
            bool(self._terminated),
            False,
            info,
        )

    def step(self, action: int | None) -> None:
        """Apply the learner's menu index, then auto-play opponents.

        Pass ``None`` only when the episode is already terminated (no-op), matching
        common AEC dead-step usage.
        """
        if self._state is None:
            raise RuntimeError("reset() must be called before step()")
        if self._terminated:
            if action is None:
                return
            raise InvalidActionError("step", "Episode already terminated")
        if action is None:
            raise InvalidActionError("step", "action is required while episode is live")
        if not isinstance(action, int) or isinstance(action, bool):
            raise InvalidActionError("step", f"action must be int index, got {action!r}")
        if action < 0 or action >= len(self._legal):
            raise InvalidActionError(
                "step",
                f"action index {action} out of range for {len(self._legal)} legal actions",
            )

        chosen: GameAction = self._legal[action].action
        self._state = self._engine.apply_action(self._state, chosen)
        self._pending_reward = 0.0

        if self._engine.is_terminal(self._state):
            self._enter_terminal()
        else:
            self._advance_to_learner_or_end()
        self._sync_agent_dicts()

    # --- internals ---------------------------------------------------------

    def _advance_to_learner_or_end(self) -> None:
        assert self._state is not None
        while not self._engine.is_terminal(self._state):
            current = self._engine.get_current_player(self._state)
            if current == self._learner_id:
                self._legal = self._engine.legal_actions(self._state, current)
                self.agent_selection = self._learner_id
                if not self._legal:
                    raise InvalidActionError(
                        "advance",
                        f"Learner {current} has no legal actions in a non-terminal state",
                    )
                return
            self._play_opponent(current)
        self._enter_terminal()

    def _play_opponent(self, player_id: str) -> None:
        assert self._state is not None
        legal = self._engine.legal_actions(self._state, player_id)
        if not legal:
            raise InvalidActionError(
                "opponent",
                f"Player {player_id} has no legal actions in a non-terminal state",
            )
        observation = self._engine.observe(self._state, player_id)
        ctx = PolicyContext(advisor=self._engine, rng=self._opp_rng)
        action_id = self._opponent.choose(observation, legal, ctx)
        action = next(entry.action for entry in legal if entry.id == action_id)
        self._state = self._engine.apply_action(self._state, action)

    def _enter_terminal(self) -> None:
        assert self._state is not None
        self._terminated = True
        self.agent_selection = self._learner_id
        self._legal = []
        payoffs = self._engine.terminal_rewards(self._state)
        self._pending_reward = float(payoffs.get(self._learner_id, 0.0))
        for pid in self.agents:
            self.rewards[pid] = float(payoffs.get(pid, 0.0))
            self.terminations[pid] = True

    def _observation_dict(self) -> ObsDict:
        assert self._state is not None
        if self._terminated:
            # Learner may not be to act; still expose last public observation.
            observation = self._engine.observe(self._state, self._learner_id)
            return {
                "observation": asdict(observation),
                "legal_action_ids": [],
            }
        observation = self._engine.observe(self._state, self._learner_id)
        return {
            "observation": asdict(observation),
            "legal_action_ids": [entry.id for entry in self._legal],
        }

    def _clear_agent_dicts(self) -> None:
        self.rewards = {pid: 0.0 for pid in self.agents}
        self.terminations = {pid: False for pid in self.agents}
        self.truncations = {pid: False for pid in self.agents}
        self.infos = {pid: {} for pid in self.agents}

    def _sync_agent_dicts(self) -> None:
        self.infos[self._learner_id] = {
            "legal_action_count": len(self._legal),
            "phase": getattr(self._state, "phase", "") if self._state else "",
            "round": int(getattr(self._state, "round", 0)) if self._state else 0,
        }
        if self._terminated and self._state is not None:
            payoffs = self._engine.terminal_rewards(self._state)
            for pid in self.agents:
                self.rewards[pid] = float(payoffs.get(pid, 0.0))
                self.terminations[pid] = True


__all__ = ["CardLabAECEnv"]
