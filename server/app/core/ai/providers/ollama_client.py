"""Ollama LLM client using httpx with native JSON / NDJSON streaming."""

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


class OllamaClient(LLMClient):
    """Async client for Ollama /api/chat endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",  # qwen2.5:7b: balanced; qwen2.5:14b: capable; llama3.2:3b: fast
        timeout: float = 120.0,
        **kwargs: Any,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def _build_options(self, temperature: float, max_tokens: int | None) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        return options

    def _http_timeout(self) -> httpx.Timeout:
        # read applies between stream chunks (prompt eval can be slow on local CPU)
        return httpx.Timeout(
            connect=10.0,
            read=self._timeout,
            write=30.0,
            pool=10.0,
        )

    def _map_http_error(self, exc: Exception) -> AIProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return AIProviderError("ollama", f"Ollama 请求超时（{self._base_url}）")
        if isinstance(exc, httpx.ConnectError):
            return AIProviderError(
                "ollama",
                f"无法连接 Ollama（{self._base_url}）。请确认 Ollama 已启动，且本机可访问该地址。",
            )
        if isinstance(exc, httpx.HTTPStatusError):
            return AIProviderError(
                "ollama",
                f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
            )
        return AIProviderError("ollama", str(exc))

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        model = kwargs.pop("model", self._model)
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", None)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": self._build_options(temperature, max_tokens),
        }

        url = f"{self._base_url}/api/chat"

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["message"]["content"]
                usage = {
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "completion_tokens": data.get("eval_count"),
                    "total_tokens": None,
                }
                logger.debug(
                    "ollama_response",
                    model=model,
                    eval_count=data.get("eval_count"),
                    eval_duration=data.get("eval_duration"),
                )
                return ChatResponse(content=content, usage=usage)
        except Exception as e:
            raise self._map_http_error(e) from e

    async def chat_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream Ollama /api/chat NDJSON chunks to the observer UI.

        Ollama emits one JSON object per line while ``stream: true``. Intermediate
        lines carry ``message.content`` deltas; the final line has ``done: true``
        and token counts.
        """
        model = kwargs.pop("model", self._model)
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", None)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": self._build_options(temperature, max_tokens),
        }

        url = f"{self._base_url}/api/chat"

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning("ollama_stream_bad_json", line=line[:200])
                            continue

                        message = data.get("message") or {}
                        content = message.get("content") or ""
                        done = bool(data.get("done"))

                        usage: dict[str, int | None] | None = None
                        if done:
                            usage = {
                                "prompt_tokens": data.get("prompt_eval_count"),
                                "completion_tokens": data.get("eval_count"),
                                "total_tokens": None,
                            }
                            logger.debug(
                                "ollama_stream_done",
                                model=model,
                                eval_count=data.get("eval_count"),
                                eval_duration=data.get("eval_duration"),
                            )

                        if content or (done and usage is not None):
                            yield StreamChunk(type="content", text=content, usage=usage)
        except Exception as e:
            raise self._map_http_error(e) from e

    def supports(self, provider: str) -> bool:
        return provider.lower() == "ollama"
