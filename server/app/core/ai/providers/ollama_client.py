"""Ollama LLM client using httpx with native JSON format."""

from __future__ import annotations

import structlog
import httpx
from typing import Any

from app.core.ai.base import ChatResponse, LLMClient
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

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        model = kwargs.pop("model", self._model)
        temperature = kwargs.pop("temperature", 0.7)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        url = f"{self._base_url}/api/chat"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
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
        except httpx.TimeoutException as e:
            raise AIProviderError("ollama", f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            raise AIProviderError(
                "ollama",
                f"Cannot connect to Ollama at {self._base_url}. Is it running?",
            ) from e
        except httpx.HTTPStatusError as e:
            raise AIProviderError(
                "ollama",
                f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            ) from e
        except Exception as e:
            raise AIProviderError("ollama", str(e)) from e

    def supports(self, provider: str) -> bool:
        return provider.lower() == "ollama"
