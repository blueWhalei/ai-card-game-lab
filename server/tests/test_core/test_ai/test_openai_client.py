"""Transport-level provider contracts without real API calls."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.core.ai.providers.openai_client import OpenAICompatibleClient
from app.utils.exceptions import (
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitExceededError,
)

SCHEMA = {"type": "json_schema", "json_schema": {"name": "action", "schema": {"type": "object"}}}
MESSAGES = [{"role": "user", "content": "choose"}]


def make_client(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> OpenAICompatibleClient:
    original = httpx.AsyncClient
    monkeypatch.setattr(
        "app.core.ai.providers.openai_client.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    return OpenAICompatibleClient(api_key="test-only")


def success(stream: bool) -> httpx.Response:
    if stream:
        events = [
            {"choices": [{"delta": {"reasoning_content": "think"}}]},
            {"choices": [{"delta": {"content": "answer"}}]},
            {
                "choices": [],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            },
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    return httpx.Response(
        200, json={"choices": [{"message": {"content": "answer"}}], "usage": {"total_tokens": 5}}
    )


async def call(client: OpenAICompatibleClient, stream: bool) -> Any:
    if stream:
        return [chunk async for chunk in client.chat_stream(MESSAGES, response_format=SCHEMA)]
    return await client.chat(MESSAGES, response_format=SCHEMA)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
async def test_http_errors_never_trigger_parameter_fallback(
    monkeypatch: pytest.MonkeyPatch, stream: bool, status: int
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": "response_format unsupported"}})

    client = make_client(monkeypatch, handler)
    error = (
        AIRateLimitExceededError
        if status == 429
        else AIProviderUnavailableError
        if status == 503
        else AIProviderError
    )
    with pytest.raises(error, match=f"HTTP {status}"):
        await call(client, stream)
    assert len(requests) == 1


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "message",
    [
        "invalid schema for response_format",
        "max_tokens must be positive",
        "unknown parameter temperature",
        "response_format validation service is unavailable",
    ],
)
async def test_unrelated_validation_does_not_drop_constraints(
    monkeypatch: pytest.MonkeyPatch, stream: bool, message: str
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json={"error": {"message": message}})

    with pytest.raises(AIProviderError, match="HTTP 400"):
        await call(make_client(monkeypatch, handler), stream)
    assert len(requests) == 1


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [400, 422])
@pytest.mark.parametrize(
    "message",
    ["response_format unsupported_parameter", "This response_format type is unavailable now"],
)
async def test_explicit_schema_rejection_retries_once(
    monkeypatch: pytest.MonkeyPatch, stream: bool, status: int, message: str
) -> None:
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        if "response_format" in payload:
            return httpx.Response(
                status,
                json={"error": {"message": message}},
            )
        return success(stream)

    result = await call(make_client(monkeypatch, handler), stream)
    assert len(payloads) == 2
    assert "response_format" not in payloads[1]
    if stream:
        assert "stream_options" in payloads[1]
        assert [chunk.text for chunk in result] == ["think", "answer", ""]
        assert result[-1].usage["total_tokens"] == 5
    else:
        assert result.content == "answer"


async def test_stream_drops_only_the_named_field_and_preserves_reasoning_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        if "stream_options" in payload:
            return httpx.Response(400, text="Unknown parameter: stream_options")
        return success(True)

    client = make_client(monkeypatch, handler)
    chunks = [
        chunk
        async for chunk in client.chat_stream(
            MESSAGES, response_format=SCHEMA, reasoning_effort="high"
        )
    ]
    assert chunks
    assert len(payloads) == 2
    assert payloads[1]["response_format"] == SCHEMA
    assert payloads[1]["reasoning_effort"] == "high"


@pytest.mark.parametrize("stream", [False, True])
async def test_timeout_does_not_retry(monkeypatch: pytest.MonkeyPatch, stream: bool) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(AIProviderError, match="timed out"):
        await call(make_client(monkeypatch, handler), stream)
    assert len(requests) == 1


async def test_stream_disconnect_surfaces_error_without_restarting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            raise httpx.ReadError("connection lost")

    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, stream=BrokenStream())

    client = make_client(monkeypatch, handler)
    chunks = []
    with pytest.raises(AIProviderError, match="connection lost"):
        async for chunk in client.chat_stream(MESSAGES):
            chunks.append(chunk.text)
    assert chunks == ["partial"]
    assert len(requests) == 1


async def test_nonstream_reasoning_fallback_and_invalid_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "", "reasoning": "fallback"}}]}
        )

    client = make_client(monkeypatch, handler)
    assert (await client.chat(MESSAGES)).content == "fallback"
    monkeypatch.undo()
    client = make_client(monkeypatch, lambda request: httpx.Response(200, text="not json"))
    with pytest.raises(AIProviderError):
        await client.chat(MESSAGES)
