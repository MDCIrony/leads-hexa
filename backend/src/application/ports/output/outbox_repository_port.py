from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from application.dtos.commands import OutboxEntry
from domain.events.lead_events import OutboundEvent


class OutboxRepositoryPort(ABC):
    @abstractmethod
    def record(self, event: OutboundEvent) -> None:
        """Write the event inside the caller's transaction.

        Not a side effect: an INSERT that a rollback takes with it, which is
        the whole point — a lead that is not saved must not be published."""

    @abstractmethod
    def list_unpublished(self, limit: int) -> List[OutboxEntry]:
        """Oldest first. Locked against another relay taking the same rows."""

    @abstractmethod
    def mark_published(self, event_id: UUID) -> None: ...

    @abstractmethod
    def mark_failed(self, event_id: UUID, error: str) -> None: ...
