from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(kw_only=True)
class DomainEvent(ABC):
    """Base class for all domain events."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_on: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def event_type(self) -> str:
        return self.__class__.__name__
