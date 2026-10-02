from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from domain.events.domain_event import DomainEvent


@dataclass(kw_only=True)
class InternalEvent(DomainEvent):
    """A fact other services of this platform consume, never a customer.

    Travels through the outbox's internal channel inside an envelope that
    already carries event_id and occurred_on, so the payload holds only the
    fact itself."""

    # None for state with no organization, e.g. the platform admin's identity.
    tenant_id: Optional[str]

    @property
    @abstractmethod
    def partition_key(self) -> str:
        """What must reach a consumer in order: one aggregate's history."""

    def as_payload(self) -> Dict[str, Any]:
        payload = super().as_payload()
        del payload["event_id"], payload["occurred_on"]
        return payload
