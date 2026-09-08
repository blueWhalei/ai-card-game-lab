"""JSON helpers for MCP tool payloads (keep agent context small)."""

from __future__ import annotations

from typing import Any

_THINKING_MAX = 500
_PROMPT_CHARS_MAX = 400


def truncate_decision_item(item: dict[str, Any]) -> dict[str, Any]:
    """Copy a decision-point row with long text fields shortened for MCP."""
    out = dict(item)
    thinking = out.get("thinking")
    if isinstance(thinking, str) and len(thinking) > _THINKING_MAX:
        out["thinking"] = thinking[:_THINKING_MAX] + "…"

    prompts = out.get("prompt_messages")
    if isinstance(prompts, list):
        compact: list[dict[str, Any]] = []
        for message in prompts:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str) and len(content) > _PROMPT_CHARS_MAX:
                compact.append(
                    {
                        "role": message.get("role"),
                        "content": content[:_PROMPT_CHARS_MAX] + "…",
                        "content_len": len(content),
                    }
                )
            else:
                compact.append(dict(message))
        out["prompt_messages"] = compact
        out["prompt_message_count"] = len(prompts)
    return out
