"""Local model verification via Ollama (decision smoke + optional full game)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_SMOKE_PROMPT = """你是斗地主 AI。当前：首出，手牌有单张 C3。
直接输出单行 JSON，无 markdown：
{"action_type":"SINGLE","cards":["C3"]}
或 {"action_type":"PASS","cards":[]}
"""


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
            {"role": "system", "content": "你是斗地主AI，只输出JSON动作。"},
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
    ok = parsed is not None and "action_type" in parsed
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
    # Normalize nested {"action": {...}}
    if "action" in data and isinstance(data["action"], dict):
        inner = data["action"]
        return {
            "action_type": str(inner.get("type") or inner.get("action_type") or ""),
            "cards": inner.get("cards") or [],
        }
    return {
        "action_type": str(data.get("action_type") or data.get("type") or ""),
        "cards": data.get("cards") or [],
    }
