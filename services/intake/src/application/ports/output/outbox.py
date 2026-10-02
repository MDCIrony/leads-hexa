from abc import ABC, abstractmethod

from domain.events.internal_event import InternalEvent


class OutboxRepositoryPort(ABC):
    @abstractmethod
    def record(self, event: InternalEvent, channel: str = "internal") -> None:
        """Write the event inside the caller's transaction, so a rollback takes it along.

        Reading and marking rows belongs to the relay's own store, not to the use cases."""
