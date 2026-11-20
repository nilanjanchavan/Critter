"""Synchronous typed event bus for Critter.

Keeps business logic and UI cleanly decoupled using a publish-subscribe pattern.
Handlers run synchronously on the calling thread (designed for GLib's main loop).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Type, TypeVar

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Event:
    """Base event payload."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def event_name(self) -> str:
        return self.__class__.__name__


E = TypeVar("E", bound=Event)
EventHandler = Callable[[Any], None]


class EventBus:
    """Synchronous publish/subscribe event bus."""

    def __init__(self) -> None:
        self._handlers: Dict[Type[Event], List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []

    def subscribe(self, event_type: Type[E], handler: Callable[[E], None]) -> Callable[[], None]:
        """Subscribe a handler to a specific event type.

        Returns an unsubscribe callback for clean disposal.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

        def unsubscribe() -> None:
            self.unsubscribe(event_type, handler)

        return unsubscribe

    def subscribe_all(self, handler: EventHandler) -> Callable[[], None]:
        """Subscribe a handler to all events (useful for logging/debugging)."""
        self._global_handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)

        return unsubscribe

    def unsubscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            if not self._handlers[event_type]:
                del self._handlers[event_type]

    def publish(self, event: Event) -> None:
        """Publish an event synchronously to all registered subscribers."""
        event_cls = type(event)
        logger.debug("Publishing event %s: %s", event_cls.__name__, event)

        # Notify specific event handlers
        handlers = list(self._handlers.get(event_cls, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.exception("Error executing event handler %r for event %s: %s", handler, event_cls.__name__, exc)

        # Notify global handlers
        for global_handler in list(self._global_handlers):
            try:
                global_handler(event)
            except Exception as exc:
                logger.exception("Error executing global handler %r for event %s: %s", global_handler, event_cls.__name__, exc)

    def clear(self) -> None:
        """Clear all subscribers."""
        self._handlers.clear()
        self._global_handlers.clear()
