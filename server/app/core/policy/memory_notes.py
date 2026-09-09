"""Rule-based opponent notes for per-experiment Policy memory."""

from __future__ import annotations

from typing import Any


def build_rule_memory_notes(
    *,
    player_id: str,
    winner_id: str | None,
    decisions: list[dict[str, Any]],
) -> str:
    """Compact structured notes from one finished game (no LLM)."""
    n = len(decisions)
    if n == 0:
        outcome = "unknown"
        if winner_id and winner_id == player_id:
            outcome = "win"
        elif winner_id:
            outcome = "lose"
        return f"Last game: {outcome}; no recorded decisions."

    losses = [float(d["ev_loss"]) for d in decisions if d.get("ev_loss") is not None]
    avg_loss = sum(losses) / len(losses) if losses else None
    fallbacks = sum(1 for d in decisions if d.get("parse_fallback"))
    if winner_id and winner_id == player_id:
        outcome = "win"
    elif winner_id:
        outcome = "lose"
    else:
        outcome = "draw_or_unknown"

    parts = [
        f"Last game: {outcome}",
        f"decisions={n}",
    ]
    if avg_loss is not None:
        parts.append(f"avg_ev_loss={avg_loss:.3f}")
    else:
        parts.append("avg_ev_loss=n/a")
    parts.append(f"parse_fallback={fallbacks}")
    return "; ".join(parts)
