from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import LeadStatus
from domain.value_objects.tenant_id import TenantId


class LeadTransitions:
    """Status transitions of Lead, split off to keep each file small.

    Not meant to be used alone: it reads the fields Lead declares."""

    tenant_id: TenantId
    status: LeadStatus
    assigned_agent_id: Optional[AgentId]
    assigned_at: Optional[datetime]
    discard_reason: Optional[str]
    disqualification_reason: Optional[str]
    updated_at: datetime

    def qualify(self) -> None:
        """NEW → QUALIFIED, with no threshold of its own.

        Viability already ruled out what cannot be worked, and the lowest band
        of the assignment rules is now the only score cut — written by the
        manager instead of frozen in the code. The old two-threshold version
        had two branches for three ranges, so a lead in between changed to
        nothing and stayed NEW forever."""
        self.status = LeadStatus.QUALIFIED

    def disqualify(self, reason: str) -> None:
        """A machine decision, carrying the rule's name as its reason.

        Distinct from discard(), where a person looked at the lead and wrote
        why. Merging them would cost the manager the only signal that tells a
        badly written rule from a genuinely bad lead."""
        self.status = LeadStatus.DISQUALIFIED
        self.disqualification_reason = reason

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
