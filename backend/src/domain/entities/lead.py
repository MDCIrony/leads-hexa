from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from uuid import UUID

from domain.value_objects.email import EmailAddress
from domain.value_objects.money import Money
from domain.value_objects.lead_id import LeadId
from domain.value_objects.tenant_id import TenantId
from domain.value_objects.agent_id import AgentId
from domain.value_objects.score import Score
from domain.value_objects.enums import LeadStatus

@dataclass
class Lead:
    id: LeadId
    tenant_id: TenantId
    first_name: str
    last_name: str
    email: EmailAddress
    company: str
    budget: Money
    industry: str
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    phone: Optional[str] = None
    score: Score = field(default_factory=Score)
    status: LeadStatus = LeadStatus.NEW
    assigned_agent_id: Optional[AgentId] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        first_name: str,
        last_name: str,
        email: Union[str, EmailAddress],
        company: str,
        budget: Union[int, float, str, Decimal, Money],
        industry: str,
        custom_attributes: Optional[Dict[str, Any]] = None,
        phone: Optional[str] = None,
        lead_id: Optional[Union[str, UUID, LeadId]] = None,
        score: Union[int, Score] = 0,
        status: Union[str, LeadStatus] = LeadStatus.NEW,
        assigned_agent_id: Optional[Union[str, UUID, AgentId]] = None,
        created_at: Optional[Union[datetime, str]] = None,
    ) -> "Lead":
        """Factory method que encapsula la construcción de Value Objects e invariantes del Lead."""
        tenant_id_vo = tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id)
        email_vo = email if isinstance(email, EmailAddress) else EmailAddress(email)
        budget_vo = budget if isinstance(budget, Money) else Money(budget)
        lead_id_vo = lead_id if isinstance(lead_id, LeadId) else LeadId(lead_id)
        score_vo = score if isinstance(score, Score) else Score(score)
        status_vo = status if isinstance(status, LeadStatus) else LeadStatus(status)

        if assigned_agent_id is None:
            agent_id_vo = None
        elif isinstance(assigned_agent_id, AgentId):
            agent_id_vo = assigned_agent_id
        else:
            agent_id_vo = AgentId(assigned_agent_id)

        if created_at is None:
            created_at_dt = datetime.now(timezone.utc)
        elif isinstance(created_at, str):
            created_at_dt = datetime.fromisoformat(created_at)
        else:
            created_at_dt = created_at

        return cls(
            id=lead_id_vo,
            tenant_id=tenant_id_vo,
            first_name=first_name,
            last_name=last_name,
            email=email_vo,
            company=company,
            budget=budget_vo,
            industry=industry,
            custom_attributes=custom_attributes or {},
            phone=phone,
            score=score_vo,
            status=status_vo,
            assigned_agent_id=agent_id_vo,
            created_at=created_at_dt,
        )

    def apply_score(self, delta: int) -> None:
        self.score = self.score.add_points(delta)

    def qualify(self, threshold_qualified: int, threshold_disqualified: int) -> None:
        if self.score.value >= threshold_qualified:
            self.status = LeadStatus.QUALIFIED
        elif self.score.value < threshold_disqualified:
            self.status = LeadStatus.DISQUALIFIED

    def assign_to_agent(self, agent_id: Union[str, UUID, AgentId]) -> None:
        if isinstance(agent_id, AgentId):
            self.assigned_agent_id = agent_id
        else:
            self.assigned_agent_id = AgentId(agent_id)
        self.status = LeadStatus.ASSIGNED
