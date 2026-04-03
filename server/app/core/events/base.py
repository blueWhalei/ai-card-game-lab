"""Base classes for domain events and event handlers.

This module provides the foundational building blocks for the event-driven
architecture in the application. All domain events inherit from ``DomainEvent``,
and all event handlers implement the ``EventHandler`` protocol.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4


@dataclass
class DomainEvent(ABC):
    """Abstract base class for all domain events.

    Domain events represent something that happened in the domain and are
    used to communicate between different parts of the system in a loosely
    coupled manner. Each event carries metadata about when it occurred
    and a unique identifier for tracing purposes.

    Subclasses should add their own fields to carry domain-specific data.
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Return a unique identifier for this event type.

        This is typically the class name or a namespaced identifier
        like 'game.ended' or 'round.completed'.
        """


@runtime_checkable
class EventHandler(Protocol):
    """Protocol for event handlers.

    Event handlers subscribe to specific event types and react when
    those events are published. Handlers can be either synchronous
    or asynchronous, depending on the use case.
    """

    @property
    def event_types(self) -> list[type[DomainEvent]]:
        """Return the list of event types this handler subscribes to."""
        ...

    def can_handle(self, event: DomainEvent) -> bool:
        """Check if this handler can process the given event.

        Args:
            event: The event to check.

        Returns:
            True if this handler can process the event.
        """
        ...

    async def handle(self, event: DomainEvent) -> None:
        """Process the given event.

        Args:
            event: The event to process.
        """
        ...


class SyncEventHandler(ABC):
    """Base class for synchronous event handlers.

    Use this when the event handling logic is CPU-bound or does not
    involve I/O operations. For I/O-bound operations, prefer using
    the async ``EventHandler`` protocol directly.
    """

    @property
    @abstractmethod
    def event_types(self) -> list[type[DomainEvent]]:
        """Return the list of event types this handler subscribes to."""

    def can_handle(self, event: DomainEvent) -> bool:
        """Check if this handler can process the given event.

        Args:
            event: The event to check.

        Returns:
            True if this handler can process the event.
        """
        return any(isinstance(event, event_type) for event_type in self.event_types)

    @abstractmethod
    def handle(self, event: DomainEvent) -> None:
        """Process the given event synchronously.

        Args:
            event: The event to process.
        """


class AsyncEventHandler(ABC):
    """Base class for asynchronous event handlers.

    Use this when the event handling logic involves I/O operations
    such as database writes, API calls, or file operations.
    """

    @property
    @abstractmethod
    def event_types(self) -> list[type[DomainEvent]]:
        """Return the list of event types this handler subscribes to."""

    def can_handle(self, event: DomainEvent) -> bool:
        """Check if this handler can process the given event.

        Args:
            event: The event to check.

        Returns:
            True if this handler can process the event.
        """
        return any(isinstance(event, event_type) for event_type in self.event_types)

    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Process the given event asynchronously.

        Args:
            event: The event to process.
        """
