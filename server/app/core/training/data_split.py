"""Deterministic validation groups; repeated deals stay on the same side."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from app.core.stats.comparison import seed_value


def validation_groups(
    game_ids: list[str], games: dict[str, dict[str, Any]], ratio: float
) -> tuple[set[str], dict[str, Any]]:
    """Group by game type and deal seed, or by game identity without a seed.

    The ratio applies to groups, not decisions. Hash ordering avoids depending
    on timestamps or the arbitrary lexical order of generated game IDs.
    """
    if not 0 < ratio <= 0.5:
        raise ValueError("Validation group ratio must be in (0, 0.5]")
    groups: dict[str, list[str]] = defaultdict(list)
    for gid in sorted(set(game_ids)):
        game = games.get(gid) or {}
        seed = seed_value((game.get("metadata") or {}).get("deal_seed"))
        key = (
            ["deal", game["game_type"], seed]
            if seed is not None and game.get("game_type")
            else ["game", gid]
        )
        groups[json.dumps(key, ensure_ascii=False)].append(gid)
    ordered = sorted(groups, key=lambda key: (hashlib.sha256(key.encode()).hexdigest(), key))
    if len(ordered) < 2:
        raise ValueError("Validation requires at least two independent deal groups")
    n = max(1, int(len(ordered) * ratio))
    selected = ordered[:n]
    members = {gid for key in selected for gid in groups[key]}
    return members, {
        "split_method": "deal_seed_group_v1",
        "group_count": len(ordered),
        "eval_group_count": n,
        "eval_groups": [{"key": json.loads(key), "game_ids": groups[key]} for key in selected],
    }
