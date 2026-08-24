from dataclasses import dataclass
from typing import Optional
from domain.events.domain_event import DomainEvent
from domain.value_objects.enums import LeadStatus


@dataclass(kw_only=True)
class LeadProcessedEvent(DomainEvent):
    """Emitted when a Lead clears the filter — ASSIGNED or UNASSIGNED.

    What a rule ruled out travels as LeadDisqualified instead: the customer
    buys the leads our rules kept, not the ones they filtered."""

    tenant_id: str
    lead_id: str
    email: Optional[str] = None
    score: int
    status: LeadStatus
    assigned_agent_id: Optional[str] = None


@dataclass(kw_only=True)
class LeadDisqualified(DomainEvent):
    """Emitted when a viability rule rules a lead out before it is scored."""

    tenant_id: str
    lead_id: str
    source_id: str
    reason: str
