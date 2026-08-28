"""OpenAI-compatible LLM client using httpx.

Supports all providers that implement the OpenAI `/chat/completions` protocol:
OpenAI, DeepSeek, Kimi (Moonshot), MiniMax, ZhipuAI, Yi, DashScope, etc.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import structlog

from app.core.ai.base import ChatResponse, LLMClient
from app.core.ai.stream_chunk import StreamChunk
from app.utils.exceptions import AIProviderError

logger = structlog.get_logger()


class OpenAICompatibleClient(LLMClient):
    """Generic async client for any OpenAI-compatible chat completions API.

    All providers that follow the ``POST /chat/completions`` protocol
    (same request/response schema, ``Bearer`` auth) can be served by
    a single instance configured with the right *provider_name*,
    *base_url* and *api_key*.
    """

    def __init__(
        self,
        provider_name: str = "openai",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",  # gpt-4o-mini: fast & cheap; gpt-4o: more capable
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> None:
        self._provider_name = provider_name.lower()
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        model = kwargs.pop("model", self._model)
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", 2048)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{self._base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                message = data["choices"][0]["message"]
                content = message.get("content") or ""
                # DeepSeek thinking / o1-style: answer may live in reasoning fields
                if not str(content).strip():
                    for key in ("reasoning_content", "reasoning"):
                        alt = message.get(key)
                        if isinstance(alt, str) and alt.strip():
                            content = alt
                            break
                usage_data = data.get("usage") or {}
                usage = {
                    "prompt_tokens": usage_data.get("prompt_tokens"),
                    "completion_tokens": usage_data.get("completion_tokens"),
                    "total_tokens": usage_data.get("total_tokens"),
                }
                logger.debug(
                    "llm_response",
                    provider=self._provider_name,
                    model=model,
                    usage=usage,
                )
                return ChatResponse(content=content, usage=usage)
        except httpx.TimeoutException as e:
            raise AIProviderError(self._provider_name, f"Request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AIProviderError(
                self._provider_name,
                f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            ) from e
        except Exception as e:
            raise AIProviderError(self._provider_name, str(e)) from e

    async def chat_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream chat completion response chunk by chunk.

        Uses Server-Sent Events (SSE) to receive streaming response from
        OpenAI-compatible APIs. Supports reasoning_content field used by
        DeepSeek R1, OpenAI o1, and other thinking models.

        Yields:
            StreamChunk objects with type "reasoning" or "content" and text.
        """
        model = kwargs.pop("model", self._model)
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", 2048)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "text/event-stream",
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # Some providers reject stream_options; retry without it on 4xx.
        include_usage = True

        url = f"{self._base_url}/chat/completions"

        try:
            while True:
                req_payload = dict(payload)
                if include_usage:
                    req_payload["stream_options"] = {"include_usage": True}
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    async with client.stream(
                        "POST", url, json=req_payload, headers=headers
                    ) as response:
                        if (
                            response.status_code >= 400
                            and include_usage
                            and response.status_code < 500
                        ):
                            body = (await response.aread())[:300]
                            logger.warning(
                                "llm_stream_options_rejected",
                                provider=self._provider_name,
                                status=response.status_code,
                                body=body.decode("utf-8", errors="replace"),
                            )
                            include_usage = False
                            continue
                        response.raise_for_status()

                        async for line in response.aiter_lines():
                            if not line:
                                continue

                            # SSE format: "data: {json}"
                            if line.startswith("data: "):
                                data_str = line[6:]  # Remove "data: " prefix

                                # Check for stream end
                                if data_str == "[DONE]":
                                    break

                                try:
                                    data = json.loads(data_str)

                                    # 提取 usage（API 在最后一个 chunk 携带）
                                    usage_data = data.get("usage")
                                    chunk_usage: dict[str, int | None] | None = None
                                    if usage_data:
                                        chunk_usage = {
                                            "prompt_tokens": usage_data.get("prompt_tokens"),
                                            "completion_tokens": usage_data.get(
                                                "completion_tokens"
                                            ),
                                            "total_tokens": usage_data.get("total_tokens"),
                                        }

                                    choices = data.get("choices") or [{}]
                                    delta = choices[0].get("delta", {}) if choices else {}

                                    # 处理推理内容（DeepSeek R1 / OpenAI o1 等）
                                    reasoning = delta.get("reasoning_content", "") or delta.get(
                                        "reasoning", ""
                                    )
                                    if reasoning:
                                        yield StreamChunk(
                                            type="reasoning", text=reasoning, usage=chunk_usage
                                        )

                                    # 处理最终答案
                                    content = delta.get("content", "")
                                    if content:
                                        yield StreamChunk(
                                            type="content", text=content, usage=chunk_usage
                                        )

                                    # usage-only chunk（choices 为空，无文本内容）
                                    if (
                                        chunk_usage is not None
                                        and not reasoning
                                        and not content
                                    ):
                                        yield StreamChunk(
                                            type="content", text="", usage=chunk_usage
                                        )

                                except json.JSONDecodeError:
                                    # Skip malformed JSON chunks
                                    continue
                        break

        except httpx.TimeoutException as e:
            raise AIProviderError(self._provider_name, f"Stream request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AIProviderError(
                self._provider_name,
                f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            ) from e
        except Exception as e:
            raise AIProviderError(self._provider_name, str(e)) from e

    def supports(self, provider: str) -> bool:
        return provider.lower() == self._provider_name


# Backward-compatible alias
OpenAIClient = OpenAICompatibleClient
