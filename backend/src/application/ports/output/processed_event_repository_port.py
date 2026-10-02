from abc import ABC, abstractmethod
from uuid import UUID


class ProcessedEventRepositoryPort(ABC):
    @abstractmethod
    def mark(self, consumer: str, event_id: UUID) -> bool:
        """Record that `consumer` handled `event_id`, inside the caller's transaction.

        True if this call inserted the row, False if it was already there: a
        redelivery. Written together with the consumer's effect so both commit
        or neither does."""
