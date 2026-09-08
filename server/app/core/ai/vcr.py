"""Record and replay LLM chat calls (VCR).

Wraps an ``LLMClient`` so production policies stay unaware. Match keys hash the
prompt, model, sampling params, and optional ``response_format``. Storage is a
JSONL cassette under ``data/vcr/`` — no DB schema.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.core.ai.base import ChatResponse, LLMClient
from app.core.ai.stream_chunk import StreamChunk
from app.utils.exceptions import VcrMissError

VcrMode = Literal["off", "record", "replay"]

_MATCH_KWARG_KEYS = ("model", "temperature", "max_tokens", "top_p", "response_format")


def match_key(
    provider: str,
    messages: list[dict[str, Any]],
    kwargs: dict[str, Any],
) -> str:
    """Stable SHA-256 of the request identity used for cassette lookup."""
    payload: dict[str, Any] = {
        "provider": provider,
        "messages": messages,
    }
    for name in _MATCH_KWARG_KEYS:
        value = kwargs.get(name)
        if value is not None:
            payload[name] = value
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _request_snapshot(
    provider: str,
    messages: list[dict[str, Any]],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "provider": provider,
        "messages": messages,
    }
    for name in _MATCH_KWARG_KEYS:
        value = kwargs.get(name)
        if value is not None:
            snapshot[name] = value
    return snapshot


def _response_payload(
    *,
    content: str,
    usage: dict[str, int | None],
    reasoning: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "content": content,
        "usage": usage,
    }
    if reasoning:
        payload["reasoning"] = reasoning
    return payload


class VcrStore:
    """JSONL cassette indexed by match key. Same key on record overwrites."""

    def __init__(self, directory: Path, cassette: str) -> None:
        self._directory = directory
        self._path = directory / f"{cassette}.jsonl"
        self._entries: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._path.is_file():
            with self._path.open(encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    key = entry.get("key")
                    if isinstance(key, str):
                        self._entries[key] = entry
        self._loaded = True

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_loaded()
            return self._entries.get(key)

    def put(self, key: str, entry: dict[str, Any]) -> None:
        with self._lock:
            self._ensure_loaded()
            self._entries[key] = entry
            self._directory.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as handle:
                for stored in self._entries.values():
                    handle.write(json.dumps(stored, ensure_ascii=False) + "\n")


class VcrLLMClient(LLMClient):
    """Delegates to an inner client while recording or replaying responses."""

    def __init__(
        self,
        inner: LLMClient,
        store: VcrStore,
        mode: Literal["record", "replay"],
        provider: str,
    ) -> None:
        if mode not in ("record", "replay"):
            raise ValueError(f"VcrLLMClient mode must be record or replay, got {mode!r}")
        self._inner = inner
        self._store = store
        self._mode = mode
        self._provider = provider

    def supports(self, provider: str) -> bool:
        return self._inner.supports(provider)

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        key = match_key(self._provider, messages, kwargs)
        if self._mode == "replay":
            return self._replay_chat(key)

        response = await self._inner.chat(messages, **kwargs)
        self._record(
            key,
            messages,
            kwargs,
            _response_payload(content=response.content, usage=response.usage),
        )
        return response

    async def chat_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        key = match_key(self._provider, messages, kwargs)
        if self._mode == "replay":
            async for chunk in self._replay_stream(key):
                yield chunk
            return

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        usage: dict[str, int | None] = {}
        async for chunk in self._inner.chat_stream(messages, **kwargs):
            if chunk.usage is not None:
                usage = dict(chunk.usage)
            if chunk.text:
                if chunk.type == "reasoning":
                    reasoning_parts.append(chunk.text)
                else:
                    content_parts.append(chunk.text)
            yield chunk

        self._record(
            key,
            messages,
            kwargs,
            _response_payload(
                content="".join(content_parts),
                usage=usage,
                reasoning="".join(reasoning_parts) or None,
            ),
        )

    def _record(
        self,
        key: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        entry = {
            "key": key,
            "request": _request_snapshot(self._provider, messages, kwargs),
            "response": response,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        self._store.put(key, entry)

    def _lookup(self, key: str) -> dict[str, Any]:
        entry = self._store.get(key)
        if entry is None:
            raise VcrMissError(key)
        response = entry.get("response")
        if not isinstance(response, dict):
            raise VcrMissError(key)
        return response

    def _replay_chat(self, key: str) -> ChatResponse:
        response = self._lookup(key)
        content = response.get("content")
        if not isinstance(content, str):
            raise VcrMissError(key)
        usage_raw = response.get("usage") or {}
        usage: dict[str, int | None] = dict(usage_raw) if isinstance(usage_raw, dict) else {}
        return ChatResponse(content=content, usage=usage)

    async def _replay_stream(self, key: str) -> AsyncGenerator[StreamChunk, None]:
        response = self._lookup(key)
        content = response.get("content")
        if not isinstance(content, str):
            raise VcrMissError(key)
        usage_raw = response.get("usage") or {}
        usage: dict[str, int | None] | None = (
            dict(usage_raw) if isinstance(usage_raw, dict) else None
        )
        reasoning = response.get("reasoning")
        if isinstance(reasoning, str) and reasoning:
            yield StreamChunk(type="reasoning", text=reasoning)
        yield StreamChunk(type="content", text=content, usage=usage)
