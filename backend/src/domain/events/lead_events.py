from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from domain.entities.lead import Lead
from domain.events.domain_event import DomainEvent
from domain.value_objects.enums import LeadStatus


@dataclass(kw_only=True)
class LeadProcessedEvent(DomainEvent):
    """Emitted when a Lead clears the filter — ASSIGNED or UNASSIGNED.

    What a rule ruled out travels as LeadDisqualified instead: the customer
    buys the leads our rules kept, not the ones they filtered.

    Carries the whole lead, not just its identifier: whoever receives it is
    outside this system and cannot call the API back to find out who it is."""

    tenant_id: str
    lead_id: str
    email: Optional[str] = None
    score: int
    status: LeadStatus
    assigned_agent_id: Optional[str] = None
    source_id: str = ""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    industry: str = ""
    # A string, never a float: the column is NUMERIC(14, 2) because a budget
    # is money, and handing it over as binary floating point throws away the
    # exactness right where the data leaves us.
    budget: str = ""
    phone: Optional[str] = None
    assigned_at: Optional[str] = None
    created_at: str = ""
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    score_breakdown: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def of(cls, lead: Lead) -> "LeadProcessedEvent":
        """Build the outbound contract from the lead it describes.

        Two use cases publish it — ingestion and manual assignment — and a
        field added on only one of them is a contract that drifts."""
        return cls(
            tenant_id=str(lead.tenant_id.value),
            lead_id=str(lead.id),
            email=str(lead.email) if lead.email else None,
            score=int(lead.score),
            status=lead.status,
            assigned_agent_id=str(lead.assigned_agent_id) if lead.assigned_agent_id else None,
            source_id=str(lead.source_id.value),
            first_name=lead.first_name,
            last_name=lead.last_name,
            company=lead.company,
            industry=lead.industry,
            budget=str(lead.budget),
            phone=lead.phone,
            assigned_at=lead.assigned_at.isoformat() if lead.assigned_at else None,
            created_at=lead.created_at.isoformat(),
            # Copied, not aliased: a handler that edits the dict it receives
            # would be editing the lead the caller still holds.
            custom_attributes=dict(lead.custom_attributes),
            score_breakdown=[applied.as_dict() for applied in lead.score_breakdown],
        )


@dataclass(kw_only=True)
class LeadDisqualified(DomainEvent):
    """Emitted when a viability rule rules a lead out before it is scored."""

    tenant_id: str
    lead_id: str
    source_id: str
    reason: str
