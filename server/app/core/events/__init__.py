"""Domain events system for the application.

This package provides a complete event-driven architecture including:
- Base classes for domain events and event handlers
- Event bus for publish-subscribe pattern
- Game-specific domain events

Usage:
    from app.core.events import (
        DomainEvent,
        EventBus,
        get_event_bus,
        GameStartedEvent,
        GameEndedEvent,
    )

    # Get the event bus
    bus = get_event_bus()

    # Subscribe a handler
    bus.subscribe(my_handler)

    # Publish an event
    event = GameStartedEvent(
        game_id="game-123",
        game_type="doudizhu",
        player_ids=["player-1", "player-2", "player-3"],
    )
    await bus.publish(event)
"""

from app.core.events.base import (
    AsyncEventHandler,
    DomainEvent,
    EventHandler,
    SyncEventHandler,
)
from app.core.events.bus import EventBus, get_event_bus, reset_event_bus
from app.core.events.game_events import (
    GameEndedEvent,
    GameErrorEvent,
    GameStartedEvent,
    PlayerActionEvent,
    RoundCompletedEvent,
)

__all__ = [
    "AsyncEventHandler",
    "DomainEvent",
    "EventBus",
    "EventHandler",
    "GameEndedEvent",
    "GameErrorEvent",
    "GameStartedEvent",
    "PlayerActionEvent",
    "RoundCompletedEvent",
    "SyncEventHandler",
    "get_event_bus",
    "reset_event_bus",
]
