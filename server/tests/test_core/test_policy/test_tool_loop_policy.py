"""ToolLoopPolicy: model requests a tool, then picks an action id."""

from __future__ import annotations

import json

import pytest

from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.policy.base import ActionChosen, Budget, ToolCall, ToolResult
from app.core.policy.tool_loop import ToolLoopPolicy
from tests.test_core.test_policy.test_llm_policy import (
    ScriptedClient,
    _reply,
    _run,
    _setup,
)


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.policy.llm.RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr("app.core.policy.tool_loop.RETRY_BACKOFF_S", 0.0)


@pytest.fixture
def engine() -> DoudizhuEngine:
    return DoudizhuEngine()


@pytest.mark.asyncio
async def test_tool_then_action(engine) -> None:
    observation, legal, ctx = _setup(engine)
    tool_name = ctx.advisor.tool_names(observation.phase)[0]
    client = ScriptedClient(
        [
            json.dumps({"tool": tool_name, "arguments": {}}),
            _reply(legal[0].id),
        ],
        stream_replies=[],  # force non-stream path via empty? use stream=False
    )
    policy = ToolLoopPolicy(client, stream=False)
    events = await _run(policy, observation, legal, ctx, Budget(max_llm_calls=4, max_tool_calls=2))
    assert any(isinstance(e, ToolCall) and e.name == tool_name for e in events)
    assert any(isinstance(e, ToolResult) for e in events)
    chosen = next(e for e in events if isinstance(e, ActionChosen))
    assert chosen.action_id == legal[0].id


@pytest.mark.asyncio
async def test_budget_exhaustion_still_chooses(engine) -> None:
    observation, legal, ctx = _setup(engine)
    tool_name = ctx.advisor.tool_names(observation.phase)[0]
    # First reply is a tool call; max_tool_calls=0 so parse should treat as
    # action-only after rebuild — send a valid action on the first call.
    client = ScriptedClient([_reply(legal[0].id)])
    policy = ToolLoopPolicy(client, stream=False)
    events = await _run(policy, observation, legal, ctx, Budget(max_llm_calls=2, max_tool_calls=0))
    chosen = next(e for e in events if isinstance(e, ActionChosen))
    assert chosen.action_id == legal[0].id
    assert not any(isinstance(e, ToolCall) for e in events)
    del tool_name


@pytest.mark.asyncio
async def test_unknown_tool_is_parse_error_then_retry(engine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient(
        [
            json.dumps({"tool": "not_a_real_tool", "arguments": {}}),
            _reply(legal[0].id),
        ]
    )
    policy = ToolLoopPolicy(client, stream=False)
    events = await _run(policy, observation, legal, ctx, Budget(max_llm_calls=3, max_tool_calls=2))
    chosen = next(e for e in events if isinstance(e, ActionChosen))
    assert chosen.action_id == legal[0].id
