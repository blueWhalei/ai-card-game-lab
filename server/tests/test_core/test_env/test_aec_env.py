"""Contract tests for CardLabAECEnv (duck-typed PettingZoo AEC)."""

from __future__ import annotations

import pytest

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.env import CardLabAECEnv
from app.core.policy.baselines import FirstActionPolicy, RandomPolicy
from app.utils.exceptions import InvalidActionError

PLAYERS = ["p1", "p2", "p3"]
LEARNER = "p1"


def _env(*, seed_opp: int = 0) -> CardLabAECEnv:
    return CardLabAECEnv(
        DoudizhuEngine(),
        PLAYERS,
        learner_id=LEARNER,
        opponent=FirstActionPolicy(),
        opponent_seed=seed_opp,
    )


def test_reset_and_full_episode_with_index_zero() -> None:
    env = _env()
    env.reset(seed=42)
    steps = 0
    final_reward = None
    for _agent in env.agent_iter(max_iter=500):
        obs, reward, term, trunc, info = env.last()
        assert trunc is False
        assert "legal_action_ids" in obs
        assert "observation" in obs
        if term:
            final_reward = reward
            break
        assert info["legal_action_count"] == len(obs["legal_action_ids"])
        assert info["legal_action_count"] >= 1
        env.step(0)
        steps += 1
    assert steps > 0
    assert final_reward is not None
    assert final_reward in (0.0, 1.0)
    assert env.terminations[LEARNER] is True
    engine = DoudizhuEngine()
    # Rebuild is not needed: compare env rewards dict to engine on env state.
    assert env._state is not None
    expected = engine.terminal_rewards(env._state)
    assert env.rewards[LEARNER] == expected[LEARNER]
    assert final_reward == expected[LEARNER]


def test_same_seed_is_reproducible_with_first_action_learner() -> None:
    def trajectory(seed: int) -> list[str]:
        env = _env()
        env.reset(seed=seed)
        ids: list[str] = []
        for _agent in env.agent_iter(max_iter=500):
            obs, _reward, term, _trunc, _info = env.last()
            if term:
                break
            ids.append(obs["legal_action_ids"][0])
            env.step(0)
        return ids

    assert trajectory(7) == trajectory(7)
    assert len(trajectory(7)) > 0


def test_invalid_action_index_raises() -> None:
    env = _env()
    env.reset(seed=1)
    obs, _r, term, _t, _i = env.last()
    assert not term
    n = len(obs["legal_action_ids"])
    with pytest.raises(InvalidActionError):
        env.step(n)
    with pytest.raises(InvalidActionError):
        env.step(-1)


def test_random_opponent_still_terminates() -> None:
    env = CardLabAECEnv(
        DoudizhuEngine(),
        PLAYERS,
        learner_id=LEARNER,
        opponent=RandomPolicy(),
        opponent_seed=99,
    )
    env.reset(seed=3)
    for _agent in env.agent_iter(max_iter=800):
        obs, _reward, term, _trunc, _info = env.last()
        if term:
            break
        env.step(0)
    assert env._terminated is True


def test_learner_must_be_a_player() -> None:
    with pytest.raises(ValueError, match="learner_id"):
        CardLabAECEnv(DoudizhuEngine(), PLAYERS, learner_id="ghost")
