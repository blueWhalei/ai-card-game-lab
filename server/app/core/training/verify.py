"""Local model verification via Ollama (decision smoke + optional full game)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_SMOKE_PROMPT = """你是斗地主 AI。当前：首出，手牌有单张 C3。
可选动作：
- `SINGLE|C3|` 出单张 C3
- `PASS||` 不出

从可选动作里选一个，把它的 id 原样填进 action_id。
直接输出单行 JSON，无 markdown：
{"thinking":"出最小单张试探","action_id":"SINGLE|C3|"}
"""


def ollama_unreachable_error(
    base_url: str,
    exc: BaseException | None = None,
) -> dict[str, str]:
    """Machine-readable verify error when Ollama is not reachable."""
    root = base_url.rstrip("/")
    code = "OLLAMA_TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "OLLAMA_UNREACHABLE"
    return {"error_code": code, "error_params": {"url": root}}


async def ollama_list_tags(base_url: str) -> list[str]:
    """Return local Ollama model names."""
    url = f"{base_url.rstrip('/')}/api/tags"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    models = data.get("models") or []
    return [str(m.get("name", "")) for m in models if m.get("name")]


async def ollama_smoke_decision(
    *,
    base_url: str,
    model_name: str,
) -> dict[str, Any]:
    """Send one decision-style prompt; parse JSON action from the reply."""
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {"role": "system", "content": "你是斗地主AI，只输出JSON决策。"},
            {"role": "user", "content": _SMOKE_PROMPT},
        ],
        "options": {"temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = str((data.get("message") or {}).get("content") or "")
    parsed = _extract_action_json(content)
    ok = parsed is not None and bool(parsed.get("action_id"))
    return {
        "ok": ok,
        "model": model_name,
        "raw": content[:1000],
        "parsed": parsed,
    }


def _extract_action_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    action_id = data.get("action_id")
    if not action_id:
        return None
    result: dict[str, Any] = {"action_id": str(action_id)}
    if "thinking" in data:
        result["thinking"] = str(data.get("thinking") or "")
    return result
