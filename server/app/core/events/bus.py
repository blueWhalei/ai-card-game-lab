"""Event bus implementation for publish-subscribe pattern.

The event bus provides a centralized mechanism for publishing and
subscribing to domain events. It supports both synchronous and
asynchronous event handlers.
"""

import asyncio
from collections import defaultdict

import structlog

from app.core.events.base import (
    AsyncEventHandler,
    DomainEvent,
    EventHandler,
    SyncEventHandler,
)

logger = structlog.get_logger()


class EventBus:
    """Central event bus for publishing and subscribing to domain events.

    The event bus implements the publish-subscribe pattern, allowing
    decoupled communication between different parts of the system.
    Handlers can be registered for specific event types and will be
    notified when events of those types are published.

    Both synchronous and asynchronous handlers are supported. When an
    event is published, all registered handlers are invoked concurrently
    (for async handlers) or sequentially (for sync handlers).
    """

    def __init__(self) -> None:
        """Initialize the event bus with empty handler registries."""
        self._async_handlers: dict[type[DomainEvent], list[AsyncEventHandler]] = (
            defaultdict(list)
        )
        self._sync_handlers: dict[type[DomainEvent], list[SyncEventHandler]] = (
            defaultdict(list)
        )
        self._protocol_handlers: dict[type[DomainEvent], list[EventHandler]] = (
            defaultdict(list)
        )

    def subscribe(self, handler: AsyncEventHandler | SyncEventHandler | EventHandler) -> None:
        """Register a handler to receive events.

        The handler will be invoked for all event types it declares
        interest in via its ``event_types`` property.

        Args:
            handler: The handler to register. Can be sync, async, or
                a Protocol-based handler.
        """
        for event_type in handler.event_types:
            if isinstance(handler, AsyncEventHandler):
                self._async_handlers[event_type].append(handler)
                logger.debug(
                    "async_handler_subscribed",
                    handler=handler.__class__.__name__,
                    event_type=event_type.__name__,
                )
            elif isinstance(handler, SyncEventHandler):
                self._sync_handlers[event_type].append(handler)
                logger.debug(
                    "sync_handler_subscribed",
                    handler=handler.__class__.__name__,
                    event_type=event_type.__name__,
                )
            else:
                self._protocol_handlers[event_type].append(handler)
                logger.debug(
                    "protocol_handler_subscribed",
                    handler=handler.__class__.__name__,
                    event_type=event_type.__name__,
                )

    def unsubscribe(self, handler: AsyncEventHandler | SyncEventHandler | EventHandler) -> None:
        """Unregister a handler from receiving events.

        Args:
            handler: The handler to unregister.
        """
        for event_type in handler.event_types:
            if isinstance(handler, AsyncEventHandler):
                if handler in self._async_handlers[event_type]:
                    self._async_handlers[event_type].remove(handler)
            elif isinstance(handler, SyncEventHandler):
                if handler in self._sync_handlers[event_type]:
                    self._sync_handlers[event_type].remove(handler)
            else:
                if handler in self._protocol_handlers[event_type]:
                    self._protocol_handlers[event_type].remove(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all registered handlers.

        All handlers registered for the event's type will be invoked.
        Async handlers are run concurrently, while sync handlers are
        run sequentially in a thread pool to avoid blocking.

        Errors in handlers are caught and logged, but do not prevent
        other handlers from being invoked.

        Args:
            event: The event to publish.
        """
        event_type = type(event)
        logger.info(
            "event_published",
            event_id=event.event_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at.isoformat(),
        )

        tasks: list[asyncio.Task[None]] = []

        for async_handler in self._async_handlers[event_type]:
            if async_handler.can_handle(event):
                tasks.append(
                    asyncio.create_task(
                        self._invoke_async_handler(async_handler, event),
                        name=f"async_handler_{async_handler.__class__.__name__}_{event.event_id}",
                    )
                )

        for sync_handler in self._sync_handlers[event_type]:
            if sync_handler.can_handle(event):
                tasks.append(
                    asyncio.create_task(
                        self._invoke_sync_handler(sync_handler, event),
                        name=f"sync_handler_{sync_handler.__class__.__name__}_{event.event_id}",
                    )
                )

        for protocol_handler in self._protocol_handlers[event_type]:
            if protocol_handler.can_handle(event):
                tasks.append(
                    asyncio.create_task(
                        self._invoke_protocol_handler(protocol_handler, event),
                        name=f"protocol_handler_{protocol_handler.__class__.__name__}_{event.event_id}",
                    )
                )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _invoke_async_handler(self, handler: AsyncEventHandler, event: DomainEvent) -> None:
        """Invoke an async handler with error handling.

        Args:
            handler: The async handler to invoke.
            event: The event to pass to the handler.
        """
        try:
            await handler.handle(event)
            logger.debug(
                "async_handler_completed",
                handler=handler.__class__.__name__,
                event_id=event.event_id,
            )
        except Exception as e:
            logger.exception(
                "async_handler_failed",
                handler=handler.__class__.__name__,
                event_id=event.event_id,
                error=str(e),
            )

    async def _invoke_sync_handler(self, handler: SyncEventHandler, event: DomainEvent) -> None:
        """Invoke a sync handler in a thread pool with error handling.

        Args:
            handler: The sync handler to invoke.
            event: The event to pass to the handler.
        """
        try:
            await asyncio.to_thread(handler.handle, event)
            logger.debug(
                "sync_handler_completed",
                handler=handler.__class__.__name__,
                event_id=event.event_id,
            )
        except Exception as e:
            logger.exception(
                "sync_handler_failed",
                handler=handler.__class__.__name__,
                event_id=event.event_id,
                error=str(e),
            )

    async def _invoke_protocol_handler(self, handler: EventHandler, event: DomainEvent) -> None:
        """Invoke a protocol-based handler with error handling.

        Args:
            handler: The protocol handler to invoke.
            event: The event to pass to the handler.
        """
        try:
            await handler.handle(event)
            logger.debug(
                "protocol_handler_completed",
                handler=handler.__class__.__name__,
                event_id=event.event_id,
            )
        except Exception as e:
            logger.exception(
                "protocol_handler_failed",
                handler=handler.__class__.__name__,
                event_id=event.event_id,
                error=str(e),
            )

    def clear(self) -> None:
        """Remove all registered handlers.

        This is primarily useful for testing purposes.
        """
        self._async_handlers.clear()
        self._sync_handlers.clear()
        self._protocol_handlers.clear()
        logger.debug("event_bus_cleared")


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the singleton event bus instance.

    Returns:
        The global EventBus instance.
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the singleton event bus instance.

    This is primarily useful for testing purposes.
    """
    global _event_bus
    _event_bus = None
