from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
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
    assigned_at: Optional[datetime] = None
    discard_reason: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

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
        assigned_at: Optional[datetime] = None,
        discard_reason: Optional[str] = None,
        updated_at: Optional[datetime] = None,
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
            assigned_at=assigned_at,
            discard_reason=discard_reason,
            updated_at=updated_at or datetime.now(timezone.utc),
            created_at=created_at_dt,
        )

    def apply_score(self, delta: int) -> None:
        self.score = self.score.add_points(delta)

    def qualify(self, threshold_qualified: int, threshold_disqualified: int) -> None:
        if self.score.value >= threshold_qualified:
            self.status = LeadStatus.QUALIFIED
        elif self.score.value < threshold_disqualified:
            self.status = LeadStatus.DISQUALIFIED

    _ASSIGNABLE = (LeadStatus.QUALIFIED, LeadStatus.UNASSIGNED)
    _DISCARDABLE = (
        LeadStatus.NEW,
        LeadStatus.QUALIFIED,
        LeadStatus.UNASSIGNED,
        LeadStatus.ASSIGNED,
    )

    def assign_to(
        self,
        agent_id: Union[str, UUID, AgentId],
        agent_tenant_id: Union[str, UUID, TenantId],
        at: Optional[datetime] = None,
    ) -> None:
        """Hand the lead to an agent for the first time.

        Refuses an already assigned lead on purpose: silently overwriting the
        previous agent is what made reassignments untraceable. Use
        reassign_to for that, which says so out loud."""
        if self.status not in self._ASSIGNABLE:
            raise DomainException(
                f"No se puede asignar un lead en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self._bind_agent(agent_id, agent_tenant_id, at)

    def reassign_to(
        self,
        agent_id: Union[str, UUID, AgentId],
        agent_tenant_id: Union[str, UUID, TenantId],
        at: Optional[datetime] = None,
    ) -> None:
        if self.status != LeadStatus.ASSIGNED:
            raise DomainException(
                f"Sólo se reasigna un lead ya asignado, no uno en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self._bind_agent(agent_id, agent_tenant_id, at)

    def unassign(self) -> None:
        if self.status != LeadStatus.ASSIGNED:
            raise DomainException(
                f"Sólo se libera un lead asignado, no uno en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self.assigned_agent_id = None
        self.assigned_at = None
        self.status = LeadStatus.UNASSIGNED
        self._touch()

    def leave_unassigned(self) -> None:
        """Qualified, but no rule produced a candidate. Needs a manager."""
        if self.status != LeadStatus.QUALIFIED:
            raise DomainException(
                f"Sólo un lead calificado queda sin asignar, no uno en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self.status = LeadStatus.UNASSIGNED
        self._touch()

    def discard(self, reason: str) -> None:
        if self.status not in self._DISCARDABLE:
            raise DomainException(
                f"No se puede descartar un lead en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        clean = (reason or "").strip()
        if not clean:
            raise DomainException(
                "El descarte exige un motivo",
                error_code="DISCARD_WITHOUT_REASON",
            )
        self.discard_reason = clean
        self.status = LeadStatus.DISCARDED
        self._touch()

    def _bind_agent(
        self,
        agent_id: Union[str, UUID, AgentId],
        agent_tenant_id: Union[str, UUID, TenantId],
        at: Optional[datetime],
    ) -> None:
        tenant = agent_tenant_id if isinstance(agent_tenant_id, TenantId) else TenantId(agent_tenant_id)
        if tenant.value != self.tenant_id.value:
            raise DomainException(
                "El asesor pertenece a otra organización",
                error_code="CROSS_TENANT_ASSIGNMENT",
            )
        self.assigned_agent_id = agent_id if isinstance(agent_id, AgentId) else AgentId(agent_id)
        self.assigned_at = at or datetime.now(timezone.utc)
        self.status = LeadStatus.ASSIGNED
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
