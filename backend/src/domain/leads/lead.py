from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from domain.leads.lead_transitions import LeadTransitions
from domain.value_objects.email import EmailAddress
from domain.value_objects.money import Money
from domain.value_objects.lead_id import LeadId
from domain.value_objects.lead_source_id import LeadSourceId
from domain.value_objects.tenant_id import TenantId
from domain.value_objects.agent_id import AgentId
from domain.value_objects.score import Score
from domain.value_objects.score_breakdown import AppliedRule
from domain.value_objects.enums import LeadStatus


@dataclass
class Lead(LeadTransitions):
    id: LeadId
    tenant_id: TenantId
    source_id: LeadSourceId
    first_name: str
    last_name: str
    company: str
    budget: Money
    industry: str
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    phone: Optional[str] = None
    email: Optional[EmailAddress] = None
    score: Score = field(default_factory=Score)
    # Stored on the lead, not recomputed from the rules: the rules that
    # produced a score can be edited or deleted afterwards, and the lead must
    # still be able to explain itself.
    score_breakdown: List[AppliedRule] = field(default_factory=list)
    status: LeadStatus = LeadStatus.NEW
    assigned_agent_id: Optional[AgentId] = None
    assigned_at: Optional[datetime] = None
    discard_reason: Optional[str] = None
    disqualification_reason: Optional[str] = None
    # The intake record it was admitted from: what makes admitting it twice impossible.
    intake_record_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        source_id: Union[str, UUID, LeadSourceId],
        first_name: str,
        last_name: str,
        company: str,
        budget: Union[int, float, str, Decimal, Money],
        industry: str,
        custom_attributes: Optional[Dict[str, Any]] = None,
        phone: Optional[str] = None,
        email: Optional[Union[str, EmailAddress]] = None,
        lead_id: Optional[Union[str, UUID, LeadId]] = None,
        score: Union[int, Score] = 0,
        score_breakdown: Optional[List[AppliedRule]] = None,
        status: Union[str, LeadStatus] = LeadStatus.NEW,
        assigned_agent_id: Optional[Union[str, UUID, AgentId]] = None,
        assigned_at: Optional[datetime] = None,
        discard_reason: Optional[str] = None,
        disqualification_reason: Optional[str] = None,
        updated_at: Optional[datetime] = None,
        created_at: Optional[Union[datetime, str]] = None,
        intake_record_id: Optional[UUID] = None,
    ) -> "Lead":
        """Factory method que encapsula la construcción de Value Objects e invariantes del Lead."""
        tenant_id_vo = tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id)
        source_id_vo = source_id if isinstance(source_id, LeadSourceId) else LeadSourceId(source_id)
        if email is None or email == "":
            # An empty CSV cell and an unfilled form field mean the same
            # thing: absence. Treating "" as invalid would raise
            # InvalidEmailException over data nobody actually wrote.
            email_vo = None
        elif isinstance(email, EmailAddress):
            email_vo = email
        else:
            email_vo = EmailAddress(email)
        budget_vo = budget if isinstance(budget, Money) else Money(budget)
        lead_id_vo = lead_id if isinstance(lead_id, LeadId) else LeadId(lead_id)
        score_vo = score if isinstance(score, Score) else Score(score)
        status_vo = status if isinstance(status, LeadStatus) else LeadStatus(status)

        agent_id_vo = (assigned_agent_id if assigned_agent_id is None or isinstance(assigned_agent_id, AgentId)
                       else AgentId(assigned_agent_id))

        if created_at is None:
            created_at_dt = datetime.now(timezone.utc)
        elif isinstance(created_at, str):
            created_at_dt = datetime.fromisoformat(created_at)
        else:
            created_at_dt = created_at

        return cls(
            id=lead_id_vo,
            tenant_id=tenant_id_vo,
            source_id=source_id_vo,
            first_name=first_name,
            last_name=last_name,
            company=company,
            budget=budget_vo,
            industry=industry,
            custom_attributes=custom_attributes or {},
            phone=phone,
            email=email_vo,
            score=score_vo,
            score_breakdown=score_breakdown or [],
            status=status_vo,
            assigned_agent_id=agent_id_vo,
            assigned_at=assigned_at,
            discard_reason=discard_reason,
            disqualification_reason=disqualification_reason,
            intake_record_id=intake_record_id,
            updated_at=updated_at or datetime.now(timezone.utc),
            created_at=created_at_dt,
        )

    def apply_score(self, delta: int) -> None:
        self.score = self.score.add_points(delta)
