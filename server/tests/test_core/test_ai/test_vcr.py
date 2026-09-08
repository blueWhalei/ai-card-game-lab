"""Tests for LLM VCR record / replay."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest

from app.core.ai.base import ChatResponse, LLMClient
from app.core.ai.stream_chunk import StreamChunk
from app.core.ai.vcr import VcrLLMClient, VcrStore, match_key
from app.utils.exceptions import VcrMissError


class _FakeClient(LLMClient):
    def __init__(self) -> None:
        self.chat_calls = 0
        self.stream_calls = 0

    def supports(self, provider: str) -> bool:
        return provider == "fake"

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        self.chat_calls += 1
        return ChatResponse(
            content='{"thinking":"ok","action_id":"a1"}',
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    async def chat_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        self.stream_calls += 1
        yield StreamChunk(type="reasoning", text="hmm")
        yield StreamChunk(type="content", text='{"thinking":"ok",')
        yield StreamChunk(
            type="content",
            text='"action_id":"a1"}',
            usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        )


def _messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "pick an action"}]


@pytest.mark.asyncio
async def test_record_then_replay_chat(tmp_path: Path) -> None:
    store = VcrStore(tmp_path, "roundtrip")
    inner = _FakeClient()
    recorder = VcrLLMClient(inner, store, "record", "openai")
    kwargs = {"model": "m", "temperature": 0.2}

    first = await recorder.chat(_messages(), **kwargs)
    assert first.content.startswith("{")
    assert inner.chat_calls == 1
    assert store.path.is_file()

    replay_inner = _FakeClient()
    replayer = VcrLLMClient(replay_inner, store, "replay", "openai")
    second = await replayer.chat(_messages(), **kwargs)
    assert second.content == first.content
    assert second.usage == first.usage
    assert replay_inner.chat_calls == 0


@pytest.mark.asyncio
async def test_replay_miss_raises(tmp_path: Path) -> None:
    store = VcrStore(tmp_path, "empty")
    client = VcrLLMClient(_FakeClient(), store, "replay", "openai")
    with pytest.raises(VcrMissError) as caught:
        await client.chat(_messages(), model="m")
    assert caught.value.code == "VCR_MISS"
    assert caught.value.key


def test_match_key_stable_and_sensitive() -> None:
    messages = _messages()
    base = {"model": "m", "temperature": 0.5, "response_format": {"type": "json_object"}}
    key_a = match_key("openai", messages, base)
    key_b = match_key("openai", messages, dict(base))
    assert key_a == key_b

    hotter = {**base, "temperature": 0.9}
    assert match_key("openai", messages, hotter) != key_a

    other_enum = {
        **base,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": {"enum": ["a1", "a2"]}},
        },
    }
    assert match_key("openai", messages, other_enum) != key_a

    assert match_key("ollama", messages, base) != key_a


@pytest.mark.asyncio
async def test_stream_aggregates_and_replays(tmp_path: Path) -> None:
    store = VcrStore(tmp_path, "stream")
    inner = _FakeClient()
    recorder = VcrLLMClient(inner, store, "record", "openai")
    kwargs = {"model": "m"}

    recorded: list[StreamChunk] = []
    async for chunk in recorder.chat_stream(_messages(), **kwargs):
        recorded.append(chunk)
    assert inner.stream_calls == 1
    assert "".join(c.text for c in recorded if c.type == "content") == (
        '{"thinking":"ok","action_id":"a1"}'
    )

    replayed: list[StreamChunk] = []
    replay_inner = _FakeClient()
    replayer = VcrLLMClient(replay_inner, store, "replay", "openai")
    async for chunk in replayer.chat_stream(_messages(), **kwargs):
        replayed.append(chunk)

    assert any(c.type == "reasoning" and c.text == "hmm" for c in replayed)
    content = next(c for c in replayed if c.type == "content")
    assert content.text == '{"thinking":"ok","action_id":"a1"}'
    assert content.usage == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }
    assert replay_inner.stream_calls == 0


@pytest.mark.asyncio
async def test_record_overwrite_same_key(tmp_path: Path) -> None:
    store = VcrStore(tmp_path, "overwrite")

    class Mutating(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.payload = "first"

        async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
            self.chat_calls += 1
            return ChatResponse(content=self.payload, usage={})

    inner = Mutating()
    recorder = VcrLLMClient(inner, store, "record", "openai")
    await recorder.chat(_messages(), model="m")
    inner.payload = "second"
    await recorder.chat(_messages(), model="m")

    lines = store.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    replayed = await VcrLLMClient(_FakeClient(), store, "replay", "openai").chat(
        _messages(), model="m"
    )
    assert replayed.content == "second"
