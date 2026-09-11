"""LLMPolicy: the paths that used to have no coverage at all.

Retry, timeout, streaming fallback, and budget exhaustion were only reachable
through a live provider before, so nothing pinned them.
"""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncGenerator, Iterable
from typing import Any

import pytest

from app.core.ai.base import ChatResponse, LLMClient
from app.core.ai.stream_chunk import StreamChunk
from app.core.engine.base import GameEngine
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.policy.base import (
    ActionChosen,
    Budget,
    LlmRequest,
    LlmUsage,
    PolicyContext,
    ThinkingDelta,
    ToolCall,
    ToolResult,
)
from app.core.policy.llm import LLMPolicy
from app.utils.exceptions import AIProviderError, InvalidActionError

USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


class ScriptedClient(LLMClient):
    """A model whose every turn is decided in advance.

    Each entry is either reply text or an exception to raise.
    """

    def __init__(
        self,
        replies: Iterable[str | Exception],
        *,
        stream_replies: Iterable[str | Exception | tuple[str, Exception]] | None = None,
        chat_delay_s: float = 0.0,
    ) -> None:
        self._replies = list(replies)
        self._stream_replies = list(stream_replies) if stream_replies is not None else None
        self._chat_delay_s = chat_delay_s
        self.chat_calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    def _next(self, queue: list[str | Exception]) -> str:
        item = queue.pop(0) if queue else AIProviderError("scripted", "out of replies")
        if isinstance(item, Exception):
            raise item
        return item

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        self.chat_calls.append({"messages": messages, "kwargs": kwargs})
        if self._chat_delay_s:
            await asyncio.sleep(self._chat_delay_s)
        return ChatResponse(content=self._next(self._replies), usage=dict(USAGE))

    async def chat_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        self.stream_calls.append({"messages": messages, "kwargs": kwargs})
        queue = self._stream_replies if self._stream_replies is not None else self._replies
        item = queue.pop(0) if queue else AIProviderError("scripted", "out of replies")
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            # Emit a fragment, then die the way a dropped SSE connection does.
            partial, error = item
            yield StreamChunk(type="content", text=partial)
            raise error
        for piece in (item[: len(item) // 2], item[len(item) // 2 :]):
            yield StreamChunk(type="content", text=piece)
        yield StreamChunk(type="content", text="", usage=dict(USAGE))

    def supports(self, provider: str) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.policy.llm.RETRY_BACKOFF_S", 0.0)


@pytest.fixture
def engine() -> DoudizhuEngine:
    return DoudizhuEngine()


def _setup(engine: GameEngine) -> tuple[Any, list[Any], PolicyContext]:
    state = engine.initialize(["p1", "p2", "p3"], seed=424242)
    player_id = engine.get_current_player(state)
    observation = engine.observe(state, player_id)
    presented, _ = engine.present_legal_actions(state, player_id)
    ctx = PolicyContext(advisor=engine, rng=random.Random(7), session_id="game_1")
    return observation, presented, ctx


def _reply(action_id: str, thinking: str = "分析") -> str:
    return json.dumps({"thinking": thinking, "action_id": action_id}, ensure_ascii=False)


async def _run(
    policy: LLMPolicy, observation: Any, legal: list[Any], ctx: PolicyContext, budget: Budget
) -> list[Any]:
    return [event async for event in policy.decide(observation, legal, budget, ctx)]


async def test_a_valid_reply_becomes_the_chosen_action(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([_reply(legal[0].id)])
    policy = LLMPolicy(client, stream=False)

    events = await _run(policy, observation, legal, ctx, Budget(max_llm_calls=1))

    chosen = events[-1]
    assert isinstance(chosen, ActionChosen)
    assert chosen.action_id == legal[0].id
    assert chosen.parse_fallback is False
    assert any(isinstance(e, LlmRequest) for e in events)
    assert any(isinstance(e, LlmUsage) and e.usage == USAGE for e in events)


async def test_the_schema_offers_exactly_the_presented_ids(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([_reply(legal[0].id)])

    await _run(LLMPolicy(client, stream=False), observation, legal, ctx, Budget(max_llm_calls=1))

    schema = client.chat_calls[0]["kwargs"]["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["action_id"]["enum"] == [entry.id for entry in legal]


async def test_streaming_emits_the_reply_as_it_arrives(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([_reply(legal[0].id)])

    events = await _run(
        LLMPolicy(client, stream=True), observation, legal, ctx, Budget(max_llm_calls=1)
    )

    deltas = [e for e in events if isinstance(e, ThinkingDelta)]
    assert len(deltas) > 1, "a streamed reply should arrive in pieces"
    assert isinstance(events[-1], ActionChosen)
    assert not client.chat_calls, "a working stream must not also make a plain call"


async def test_a_broken_stream_falls_back_to_one_plain_call(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient(
        [_reply(legal[0].id)],
        stream_replies=[AIProviderError("scripted", "SSE died")],
    )

    events = await _run(
        LLMPolicy(client, stream=True), observation, legal, ctx, Budget(max_llm_calls=1)
    )

    chosen = events[-1]
    assert isinstance(chosen, ActionChosen)
    assert chosen.parse_fallback is False
    assert len(client.chat_calls) == 1


async def test_partial_text_from_a_dead_stream_is_not_parsed_with_the_retry(
    engine: DoudizhuEngine,
) -> None:
    """The abandoned stream's fragment must not be concatenated onto the retry."""
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient(
        [_reply(legal[0].id)],
        stream_replies=[('{"thinking":"半句', AIProviderError("scripted", "SSE died"))],
    )

    events = await _run(
        LLMPolicy(client, stream=True), observation, legal, ctx, Budget(max_llm_calls=1)
    )

    chosen = events[-1]
    assert isinstance(chosen, ActionChosen)
    assert chosen.raw_response == _reply(legal[0].id)


async def test_a_failed_call_is_retried_within_the_budget(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([AIProviderError("scripted", "boom"), _reply(legal[0].id)])

    events = await _run(
        LLMPolicy(client, stream=False), observation, legal, ctx, Budget(max_llm_calls=3)
    )

    chosen = events[-1]
    assert isinstance(chosen, ActionChosen)
    assert chosen.parse_fallback is False
    assert len(client.chat_calls) == 2


async def test_an_unparseable_reply_is_retried(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient(["我再想想", _reply(legal[0].id)])

    events = await _run(
        LLMPolicy(client, stream=False), observation, legal, ctx, Budget(max_llm_calls=2)
    )

    assert len(client.chat_calls) == 2
    assert isinstance(events[-1], ActionChosen)
    assert events[-1].parse_fallback is False


async def test_the_call_budget_is_a_hard_cap(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([AIProviderError("scripted", "boom")] * 10)

    await _run(LLMPolicy(client, stream=False), observation, legal, ctx, Budget(max_llm_calls=2))

    assert len(client.chat_calls) == 2


async def test_an_exhausted_budget_rescues_with_a_flagged_legal_move(
    engine: DoudizhuEngine,
) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([AIProviderError("scripted", "boom")] * 5)

    events = await _run(
        LLMPolicy(client, stream=False), observation, legal, ctx, Budget(max_llm_calls=2)
    )

    chosen = events[-1]
    assert isinstance(chosen, ActionChosen)
    assert chosen.parse_fallback is True, "a rescue is not a decision by the model"
    assert chosen.action_id in {entry.id for entry in legal}


async def test_a_slow_call_times_out_and_still_yields_a_move(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([_reply(legal[0].id)], chat_delay_s=0.5)

    events = await _run(
        LLMPolicy(client, stream=False),
        observation,
        legal,
        ctx,
        Budget(max_llm_calls=1, timeout_s=0.01),
    )

    chosen = events[-1]
    assert isinstance(chosen, ActionChosen)
    assert chosen.parse_fallback is True


async def test_tools_run_within_budget_and_reach_the_prompt(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([_reply(legal[0].id)])

    events = await _run(
        LLMPolicy(client, stream=False),
        observation,
        legal,
        ctx,
        Budget(max_llm_calls=1, max_tool_calls=2),
    )

    calls = [e for e in events if isinstance(e, ToolCall)]
    results = [e for e in events if isinstance(e, ToolResult)]
    assert [call.name for call in calls] == ["analyze_hand"], "bidding has no win rate yet"
    assert results[0].result["text"]
    user_message = client.chat_calls[0]["messages"][1]["content"]
    assert "## AI分析" in user_message
    assert results[0].result["text"] in user_message


async def test_no_tools_run_when_the_budget_forbids_it(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([_reply(legal[0].id)])

    events = await _run(
        LLMPolicy(client, stream=False),
        observation,
        legal,
        ctx,
        Budget(max_llm_calls=1, max_tool_calls=0),
    )

    assert not [e for e in events if isinstance(e, ToolCall)]


async def test_the_menu_of_ids_is_in_the_prompt(engine: DoudizhuEngine) -> None:
    observation, legal, ctx = _setup(engine)
    client = ScriptedClient([_reply(legal[0].id)])

    await _run(LLMPolicy(client, stream=False), observation, legal, ctx, Budget(max_llm_calls=1))

    user_message = client.chat_calls[0]["messages"][1]["content"]
    for entry in legal:
        assert f"`{entry.id}`" in user_message


async def test_an_empty_action_list_is_refused(engine: DoudizhuEngine) -> None:
    observation, _legal, ctx = _setup(engine)
    policy = LLMPolicy(ScriptedClient([]), stream=False)

    with pytest.raises(InvalidActionError):
        await policy.decide_action(observation, [], Budget(), ctx)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("kind", ["llm", "tool_loop", "search"])
@pytest.mark.parametrize("limited", [False, True])
async def test_nonretryable_failure_stops_all_policy_calls(
    engine: DoudizhuEngine, stream: bool, kind: str, limited: bool
) -> None:
    from app.core.policy.search import SearchAugmentedPolicy
    from app.core.policy.tool_loop import ToolLoopPolicy
    from app.utils.exceptions import AIRateLimitExceededError

    error = (
        AIRateLimitExceededError("scripted", "HTTP 429")
        if limited
        else AIProviderError("scripted", "HTTP 401", retryable=False)
    )
    client = ScriptedClient([error], stream_replies=[error])
    policy_class = {"llm": LLMPolicy, "tool_loop": ToolLoopPolicy, "search": SearchAugmentedPolicy}[
        kind
    ]
    policy = policy_class(client, provider="scripted", model_name="model", stream=stream)
    observation, legal, ctx = _setup(engine)
    with pytest.raises(type(error)):
        _ = [
            event async for event in policy.decide(observation, legal, Budget(max_llm_calls=3), ctx)
        ]
    assert len(client.stream_calls) == int(stream)
    assert len(client.chat_calls) == int(not stream)
