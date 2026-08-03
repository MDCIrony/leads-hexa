from dataclasses import dataclass
from typing import Optional
from domain.events.domain_event import DomainEvent
from domain.value_objects.enums import LeadStatus


@dataclass(kw_only=True)
class LeadProcessedEvent(DomainEvent):
    """Emitted when a Lead completes its processing cycle."""

    tenant_id: str
    lead_id: str
    email: str
    score: int
    status: LeadStatus
    assigned_agent_id: Optional[str] = None
