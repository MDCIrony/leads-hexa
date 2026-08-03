from abc import ABC, abstractmethod
from domain.events.domain_event import DomainEvent


class DomainEventPublisherPort(ABC):
    """Output port for publishing domain events."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to be processed by subscribed handlers."""
        pass
