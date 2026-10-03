from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass(frozen=True)
class OutboxEntry:
    """One row of the transactional outbox, read back for delivery.

    Delivery mechanics, not a domain concept — the outbox doesn't know what
    a lead is, only that this payload needs to reach a transport."""

    id: UUID
    # None for state with no organization, e.g. the platform admin's identity.
    tenant_id: Optional[str]
    partition_key: str
    event_type: str
    payload: Dict[str, Any]
    occurred_on: datetime
    channel: str = "product"
    correlation_id: Optional[str] = None
