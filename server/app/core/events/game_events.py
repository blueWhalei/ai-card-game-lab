"""Game-related domain events.

This module defines domain events specific to game lifecycle and gameplay.
These events are published when significant game state changes occur.
"""

from dataclasses import dataclass, field
from typing import Any

from app.core.events.base import DomainEvent


@dataclass
class GameStartedEvent(DomainEvent):
    """Event published when a new game is started.

    This event is emitted after a game has been initialized and is
    ready to begin. It contains information about the game setup
    including players and game type.
    """

    game_id: str = ""
    game_type: str = ""
    player_ids: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "game.started"


@dataclass
class GameEndedEvent(DomainEvent):
    """Event published when a game has concluded.

    This event is emitted when a game reaches a terminal state.
    It contains information about the outcome including the winner
    and game statistics.
    """

    game_id: str = ""
    game_type: str = ""
    winner_id: str | None = None
    winner_role: str | None = None
    total_rounds: int = 0
    duration_seconds: float = 0.0
    player_stats: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "game.ended"


@dataclass
class RoundCompletedEvent(DomainEvent):
    """Event published when a game round is completed.

    This event is emitted after each round of gameplay, capturing
    the actions taken and the resulting state changes.
    """

    game_id: str = ""
    game_type: str = ""
    round_number: int = 0
    player_id: str = ""
    action_type: str = ""
    action_cards: list[str] = field(default_factory=list)
    action_target: str | None = None
    state_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "round.completed"


@dataclass
class PlayerActionEvent(DomainEvent):
    """Event published when a player takes an action.

    This event is emitted before the action is applied to the game state,
    allowing handlers to validate or log the action.
    """

    game_id: str = ""
    game_type: str = ""
    round_number: int = 0
    player_id: str = ""
    action_type: str = ""
    action_cards: list[str] = field(default_factory=list)
    action_target: str | None = None
    thinking: str | None = None
    response_time_ms: float | None = None

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "player.action"


@dataclass
class GameErrorEvent(DomainEvent):
    """Event published when a game encounters an error.

    This event is emitted when an error occurs during gameplay that
    doesn't necessarily terminate the game but should be logged or
    handled by error handlers.
    """

    game_id: str = ""
    game_type: str = ""
    error_type: str = ""
    error_message: str = ""
    error_context: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True

    @property
    def event_type(self) -> str:
        """Return the event type identifier."""
        return "game.error"
