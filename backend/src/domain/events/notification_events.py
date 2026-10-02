from dataclasses import dataclass
from typing import Optional
from domain.events.internal_event import InternalEvent

# Identifiers travel as str, same as LeadProcessedEvent: an event is a
# message, not a reference to a live object.


@dataclass(kw_only=True)
class _LeadEvent(InternalEvent):
    tenant_id: str
    lead_id: str

    @property
    def partition_key(self) -> str:
        return self.lead_id


@dataclass(kw_only=True)
class LeadAssigned(_LeadEvent):
    """Emitted when the routing engine finds an agent for a lead."""

    agent_id: str


@dataclass(kw_only=True)
class LeadReassigned(_LeadEvent):
    """Emitted when a manager hands an already-assigned lead to another agent."""

    agent_id: str
    previous_agent_id: Optional[str] = None


@dataclass(kw_only=True)
class LeadLeftUnassigned(_LeadEvent):
    """Emitted when a qualified lead finds no eligible agent and needs a manager."""


@dataclass(kw_only=True)
class IntakeRejected(InternalEvent):
    """Emitted when an incoming payload fails validation and cannot become a lead."""

    tenant_id: str
    intake_record_id: str
    reason: str

    @property
    def partition_key(self) -> str:
        return self.intake_record_id
