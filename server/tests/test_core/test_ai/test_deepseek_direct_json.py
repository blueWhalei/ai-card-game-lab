"""Opt-in direct JSON remains explicit, provider-specific and locally validated."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError

from app.core.ai.parsers.action_id_parser import ActionIdParser
from app.core.ai.providers.openai_client import OpenAICompatibleClient
from app.core.policy.llm import LLMPolicy
from app.schemas.experiment_config import ModelConfig
from app.utils.exceptions import AIParseError


@pytest.mark.parametrize("stream", [False, True])
async def test_direct_json_reaches_transport(monkeypatch: pytest.MonkeyPatch, stream: bool) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if stream:
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    client = OpenAICompatibleClient(provider_name="deepseek")
    policy = LLMPolicy(
        client,
        provider="deepseek",
        deepseek_direct_json=True,
        max_tokens=512,
        reasoning_effort="high",
    )
    kwargs = policy._call_kwargs(["PASS"])
    if stream:
        _ = [
            chunk
            async for chunk in client.chat_stream([{"role": "user", "content": "JSON"}], **kwargs)
        ]
    else:
        await client.chat([{"role": "user", "content": "JSON"}], **kwargs)
    assert len(requests) == 1
    assert requests[0]["thinking"] == {"type": "disabled"}
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert requests[0]["max_tokens"] == 512
    assert "reasoning_effort" not in requests[0]


@pytest.mark.parametrize("provider,enabled", [("deepseek", False), ("openai", True)])
def test_defaults_and_other_providers_keep_schema(provider: str, enabled: bool) -> None:
    policy = LLMPolicy(MagicMock(), provider=provider, deepseek_direct_json=enabled)
    kwargs = policy._call_kwargs(["PASS"])
    assert kwargs["response_format"]["type"] == "json_schema"
    assert "thinking" not in kwargs


def test_json_mode_does_not_accept_illegal_actions() -> None:
    with pytest.raises(AIParseError):
        ActionIdParser().parse('{"action_id":"illegal"}', ["PASS"])


def test_config_rejects_wrong_provider() -> None:
    with pytest.raises(ValidationError):
        ModelConfig(provider="openai", model_name="test", deepseek_direct_json=True)
