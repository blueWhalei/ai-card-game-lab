"""Unit tests for OllamaClient streaming."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.ai.providers.ollama_client import OllamaClient
from app.utils.exceptions import AIProviderError


def _ndjson_lines(chunks: list[dict[str, Any]]) -> bytes:
    return b"".join((json.dumps(c) + "\n").encode("utf-8") for c in chunks)


@pytest.mark.asyncio
async def test_chat_stream_yields_content_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _ndjson_lines(
        [
            {"message": {"role": "assistant", "content": "hel"}, "done": False},
            {"message": {"role": "assistant", "content": "lo"}, "done": False},
            {
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "prompt_eval_count": 12,
                "eval_count": 2,
            },
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["stream"] is True
        assert payload["options"]["temperature"] == 0.2
        assert payload["options"]["num_predict"] == 64
        return httpx.Response(200, content=body)

    original_init = httpx.AsyncClient.__init__

    def patched_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    client = OllamaClient(base_url="http://ollama.test", timeout=30.0)
    texts: list[str] = []
    last_usage: dict[str, int | None] | None = None
    async for chunk in client.chat_stream(
        [{"role": "user", "content": "hi"}],
        model="cardlab-test",
        temperature=0.2,
        max_tokens=64,
    ):
        if chunk.text:
            texts.append(chunk.text)
        if chunk.usage is not None:
            last_usage = chunk.usage

    assert "".join(texts) == "hello"
    assert last_usage == {
        "prompt_tokens": 12,
        "completion_tokens": 2,
        "total_tokens": None,
    }


@pytest.mark.asyncio
async def test_chat_stream_maps_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    original_init = httpx.AsyncClient.__init__

    def patched_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    client = OllamaClient(base_url="http://ollama.test")
    with pytest.raises(AIProviderError, match="无法连接 Ollama"):
        async for _ in client.chat_stream([{"role": "user", "content": "hi"}]):
            pass
