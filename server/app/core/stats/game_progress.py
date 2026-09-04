"""Live-game progress snapshot for experiment lists (one sentence on the UI)."""

from __future__ import annotations

from typing import Any


def resolve_progress_phase(game_phase: str | None) -> str:
    """Map a stored decision phase onto the list vocabulary."""
    phase = (game_phase or "").strip()
    if phase == "bidding":
        return "bidding"
    if phase == "endgame":
        return "endgame"
    if phase:
        return "playing"
    return "queued"


def build_game_progress(
    *,
    game_phase: str | None = None,
    round_number: int | None = None,
    player_id: str | None = None,
) -> dict[str, Any]:
    """Structured progress for one game. Missing moves → queued."""
    if not (game_phase or "").strip() and round_number is None:
        return {"phase": "queued", "round": None, "player_id": None}
    return {
        "phase": resolve_progress_phase(game_phase),
        "round": round_number,
        "player_id": player_id,
    }
