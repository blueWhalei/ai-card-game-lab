"""Player-config policy kinds (live seats), distinct from pack ``kind`` strings."""

from __future__ import annotations

from typing import Any, Literal

PlayerPolicyKind = Literal["llm", "tool_loop", "search", "heuristic", "random", "first"]

PLAYER_POLICY_KINDS: frozenset[str] = frozenset(
    {"llm", "tool_loop", "search", "heuristic", "random", "first"}
)
BASELINE_POLICY_KINDS: frozenset[str] = frozenset({"heuristic", "random", "first"})
LLM_POLICY_KINDS: frozenset[str] = frozenset({"llm", "tool_loop", "search"})


def is_baseline_policy_kind(kind: str) -> bool:
    return kind in BASELINE_POLICY_KINDS


def is_llm_policy_kind(kind: str) -> bool:
    return kind in LLM_POLICY_KINDS


def normalize_player_policy_kind(raw: Any, *, default: str = "llm") -> str:
    """Return a known player policy kind, or *default* when missing/blank/unknown."""
    kind = str(raw or "").strip()
    if not kind:
        return default
    if kind in PLAYER_POLICY_KINDS:
        return kind
    return default


def baseline_placeholder_model_config(kind: str) -> dict[str, Any]:
    """Minimal model_config so list UIs and legacy readers still see a row."""
    return {
        "provider": "baseline",
        "model_name": kind,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 1,
    }
