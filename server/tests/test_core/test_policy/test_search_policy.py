"""SearchAugmentedPolicy picks the highest-scored LLM candidate."""

from __future__ import annotations

import json

import pytest

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.policy.base import ActionChosen, Budget, PolicyContext
from app.core.policy.search import SearchAugmentedPolicy
from tests.test_core.test_policy.test_llm_policy import ScriptedClient, _run, _setup


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.policy.llm.RETRY_BACKOFF_S", 0.0)


@pytest.fixture
def engine() -> DoudizhuEngine:
    return DoudizhuEngine()


@pytest.mark.asyncio
async def test_search_picks_higher_scored_candidate(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    assert len(legal) >= 2
    low, high = legal[0].id, legal[1].id
    client = ScriptedClient([json.dumps({"thinking": "two options", "candidates": [low, high]})])

    def score_actions(_obs, _legal, candidates):  # type: ignore[no-untyped-def]
        return {low: 0.1, high: 0.9}

    ctx = PolicyContext(
        advisor=ctx.advisor,
        rng=ctx.rng,
        session_id=ctx.session_id,
        score_actions=score_actions,
    )
    policy = SearchAugmentedPolicy(client, stream=False, search_k=3)
    events = await _run(policy, observation, legal, ctx, Budget(max_llm_calls=2))
    chosen = next(e for e in events if isinstance(e, ActionChosen))
    assert chosen.action_id == high
