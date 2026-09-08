"""Dou Dizhu seat-as-landlord counts from persisted game rows.

Pure helpers for experiment aggregates — no DB access.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

# Roles that count as a decisive finished Dou Dizhu game.
DOUDIZHU_DECISIVE_ROLES: frozenset[str] = frozenset({"landlord", "peasant"})


def _parse_metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def seat_as_landlord_counts(
    games: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, int], dict[str, int]]:
    """Return ``(games_by_player, wins_by_player)`` from ``metadata.landlord_id``.

    Only finished decisive games (winner_role landlord/peasant) are counted.
    """
    games_by: dict[str, int] = {}
    wins_by: dict[str, int] = {}
    for g in games:
        status = str(g.get("status") or "")
        role = str(g.get("winner_role") or "") if g.get("winner_role") else ""
        if status != "finished" or role not in DOUDIZHU_DECISIVE_ROLES:
            continue
        meta = _parse_metadata(g.get("metadata"))
        landlord_id = meta.get("landlord_id")
        if not landlord_id:
            continue
        lid = str(landlord_id)
        games_by[lid] = games_by.get(lid, 0) + 1
        winner_id = g.get("winner_id")
        if winner_id and str(winner_id) == lid:
            wins_by[lid] = wins_by.get(lid, 0) + 1
    return games_by, wins_by
