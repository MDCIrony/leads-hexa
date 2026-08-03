from typing import Callable, Dict, List, Type
from application.ports.output.domain_event_publisher_port import DomainEventPublisherPort
from domain.events.domain_event import DomainEvent


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
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            handler(event)
