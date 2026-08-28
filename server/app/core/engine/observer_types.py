"""Universal observer snapshot protocol for game UI.

Frontend GenericBoard consumes this shape only — engines must emit it from
``get_public_info(..., is_observer=True)``.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ObserverLastAction(TypedDict, total=False):
    type: str
    cards: list[str]
    label: str


class ObserverPlayer(TypedDict, total=False):
    id: str
    name: str
    role: str
    is_active: bool
    hand_count: int
    hand_cards: list[str]
    badges: list[str]
    last_action: ObserverLastAction


class ObserverTableSlot(TypedDict, total=False):
    key: str
    label: str
    cards: list[str]


class ObserverTable(TypedDict, total=False):
    slots: list[ObserverTableSlot]


class ObserverSnapshot(TypedDict, total=False):
    game_type: str
    phase: str
    round: int
    current_player_id: str | None
    players: list[ObserverPlayer]
    table: ObserverTable
    extras: dict[str, Any]
