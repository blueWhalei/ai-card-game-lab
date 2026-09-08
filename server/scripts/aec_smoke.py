"""Smoke: CardLabAECEnv with index-0 learner and heuristic opponents."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `poetry run python scripts/aec_smoke.py` from server/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.env import CardLabAECEnv
from app.core.policy.baselines import HeuristicPolicy


def main() -> None:
    env = CardLabAECEnv(
        DoudizhuEngine(),
        ["p1", "p2", "p3"],
        learner_id="p1",
        opponent=HeuristicPolicy(),
        opponent_seed=0,
    )
    env.reset(seed=42)
    for steps, _agent in enumerate(env.agent_iter()):
        _obs, reward, term, _trunc, info = env.last()
        if term:
            print(f"done steps={steps} reward={reward} info={info}")
            break
        env.step(0)


if __name__ == "__main__":
    main()
