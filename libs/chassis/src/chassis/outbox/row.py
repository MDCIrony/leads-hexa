from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class OutboxRow:
    id: UUID
    channel: str
    tenant_id: Optional[str]
    partition_key: str
    event_type: str
    payload: dict
    occurred_on: datetime
    correlation_id: Optional[str]
