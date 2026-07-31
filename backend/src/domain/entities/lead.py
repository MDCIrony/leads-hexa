from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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
