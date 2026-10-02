import abc
from uuid import UUID


class ProcessedEventRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def mark(self, consumer: str, event_id: UUID) -> bool:
        """Records the event for the consumer; False when it was already recorded."""
