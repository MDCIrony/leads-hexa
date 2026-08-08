from dataclasses import dataclass
from typing import Optional
from domain.events.domain_event import DomainEvent

# Identifiers travel as str, same as LeadProcessedEvent: an event is a
# message, not a reference to a live object.


@dataclass(kw_only=True)
class LeadAssigned(DomainEvent):
    """Emitted when the routing engine finds an agent for a lead."""

    tenant_id: str
    lead_id: str
    agent_id: str


@dataclass(kw_only=True)
class LeadReassigned(DomainEvent):
    """Emitted when a manager hands an already-assigned lead to another agent."""

    tenant_id: str
    lead_id: str
    agent_id: str
    previous_agent_id: Optional[str] = None


@dataclass(kw_only=True)
class LeadLeftUnassigned(DomainEvent):
    """Emitted when a qualified lead finds no eligible agent and needs a manager."""

    tenant_id: str
    lead_id: str


@dataclass(kw_only=True)
class IntakeRejected(DomainEvent):
    """Emitted when an incoming payload fails validation and cannot become a lead."""

    tenant_id: str
    intake_record_id: str
    reason: str
