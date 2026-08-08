import logging
from typing import Callable, Dict, List, Type
from application.ports.output.domain_event_publisher_port import DomainEventPublisherPort
from domain.events.domain_event import DomainEvent

_LOGGER = logging.getLogger(__name__)


class InMemoryEventPublisher(DomainEventPublisherPort):
    """In-memory implementation of DomainEventPublisherPort."""

    def __init__(self) -> None:
        self._handlers: Dict[Type[DomainEvent], List[Callable[[DomainEvent], None]]] = {}

    def subscribe(
        self, event_type: Type[DomainEvent], handler: Callable[[DomainEvent], None]
    ) -> None:
        """Subscribe a handler function to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers for its type."""
        for handler in self._handlers.get(type(event), []):
            try:
                handler(event)
            except Exception:
                # A failing side effect must not undo work that is already
                # committed, nor stop the remaining handlers.
                _LOGGER.error(
                    "Handler %s failed for %s", handler, event.event_type, exc_info=True
                )
