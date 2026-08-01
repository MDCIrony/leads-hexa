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
        tenant_id: Union[str, UUID],
        first_name: str,
        last_name: str,
        email: str,
        company: str,
        budget: Union[int, float, str, Decimal],
        industry: str,
        custom_attributes: Optional[Dict[str, Any]] = None,
        phone: Optional[str] = None,
        lead_id: Optional[Union[str, UUID]] = None,
    ) -> "Lead":
        """Factory method que encapsula la construcción de Value Objects e invariantes del Lead."""
        return cls(
            id=LeadId(lead_id),
            tenant_id=TenantId(tenant_id),
            first_name=first_name,
            last_name=last_name,
            email=EmailAddress(email),
            company=company,
            budget=Money(budget),
            industry=industry,
            custom_attributes=custom_attributes or {},
            phone=phone,
            score=Score(0),
            status=LeadStatus.NEW,
        )

    def apply_score(self, delta: int) -> None:
        self.score = self.score.add_points(delta)

    def qualify(self, threshold_qualified: int, threshold_disqualified: int) -> None:
        if self.score.value >= threshold_qualified:
            self.status = LeadStatus.QUALIFIED
        elif self.score.value < threshold_disqualified:
            self.status = LeadStatus.DISQUALIFIED

    def assign_to_agent(self, agent_id: AgentId) -> None:
        self.assigned_agent_id = agent_id
        self.status = LeadStatus.ASSIGNED
