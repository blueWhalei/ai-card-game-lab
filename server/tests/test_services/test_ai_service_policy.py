"""AIService as a consumer of the policy event stream."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from app.core.ai.base import ChatResponse, LLMClient
from app.core.ai.prompt import PromptBuilder
from app.core.ai.stream_chunk import StreamChunk
from app.core.engine.doudizhu.engine import DoudizhuEngine
from app.core.training.data_quality import evaluate_train_usable
from app.services.ai_service import AIService
from app.utils.exceptions import AIProviderError

PLAYER_CONFIG = {
    "name": "tester",
    "model_config": {"provider": "openai", "model_name": "gpt-4o-mini", "temperature": 0.7},
}


class FakeClient(LLMClient):
    def __init__(self, reply: str | Exception) -> None:
        self._reply = reply

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        if isinstance(self._reply, Exception):
            raise self._reply
        return ChatResponse(
            content=self._reply,
            usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        )

    async def chat_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        if isinstance(self._reply, Exception):
            raise self._reply
        yield StreamChunk(type="reasoning", text="让我想想。")
        yield StreamChunk(type="content", text=self._reply)

    def supports(self, provider: str) -> bool:
        return True


class FakeFactory:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def create(self, provider: str) -> LLMClient:
        return self._client


@pytest.fixture
def engine() -> DoudizhuEngine:
    return DoudizhuEngine()


def _service(reply: str | Exception) -> AIService:
    return AIService(
        llm_factory=FakeFactory(FakeClient(reply)),  # type: ignore[arg-type]
        prompt_builder=PromptBuilder(),
    )


def _table(engine: DoudizhuEngine) -> tuple[Any, str, list[Any]]:
    state = engine.initialize(["p1", "p2", "p3"], seed=424242)
    player_id = engine.get_current_player(state)
    return state, player_id, engine.get_legal_actions(state, player_id)


async def test_a_chosen_id_becomes_an_applicable_action(engine: DoudizhuEngine) -> None:
    state, player_id, legal = _table(engine)
    target = engine.legal_actions(state, player_id)[0]
    service = _service(json.dumps({"thinking": "叫3分", "action_id": target.id}))

    result = await service.get_decision(
        state=state,
        engine=engine,
        player_id=player_id,
        player_config=PLAYER_CONFIG,
        legal_actions=legal,
    )

    assert result.parser_ok is True
    assert result.thinking == "叫3分"
    assert result.usage["total_tokens"] == 10
    assert result.messages, "the prompt has to reach the observer payload"
    assert result.prompt_preview
    # The action must be applicable, not merely well-formed.
    engine.apply_action(state, result.action)


async def test_streamed_chunks_keep_their_channel(engine: DoudizhuEngine) -> None:
    state, player_id, legal = _table(engine)
    target = engine.legal_actions(state, player_id)[0]
    service = _service(json.dumps({"thinking": "叫3分", "action_id": target.id}))

    seen: list[StreamChunk] = []
    await service.get_decision_streaming(
        state=state,
        engine=engine,
        player_id=player_id,
        player_config=PLAYER_CONFIG,
        legal_actions=legal,
        on_chunk=seen.append,
    )

    assert [chunk.type for chunk in seen] == ["reasoning", "content"]


async def test_tool_output_reaches_the_result(engine: DoudizhuEngine) -> None:
    state, player_id, legal = _table(engine)
    target = engine.legal_actions(state, player_id)[0]
    service = _service(json.dumps({"thinking": "叫3分", "action_id": target.id}))

    result = await service.get_decision(
        state=state,
        engine=engine,
        player_id=player_id,
        player_config=PLAYER_CONFIG,
        legal_actions=legal,
    )

    assert result.tool_results is not None
    assert "hand_analysis" in result.tool_results
    assert result.tool_results["tool_analysis"]


async def test_a_rescued_move_is_reported_as_a_parse_failure(engine: DoudizhuEngine) -> None:
    state, player_id, legal = _table(engine)
    service = _service(AIProviderError("openai", "down"))

    result = await service.get_decision(
        state=state,
        engine=engine,
        player_id=player_id,
        player_config=PLAYER_CONFIG,
        legal_actions=legal,
    )

    assert result.parser_ok is False
    engine.apply_action(state, result.action)


def test_a_rescued_move_is_never_training_data() -> None:
    """The structural signal decides, not the wording of the thinking text."""
    usable, reason = evaluate_train_usable(
        action_id="PASS||",
        legal_action_ids=["PASS||"],
        prompt_messages=[{"role": "user", "content": "pick"}],
        parse_fallback=True,
    )

    assert usable is False
    assert reason == "rescue_action"
