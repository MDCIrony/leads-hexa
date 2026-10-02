from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId

_NEVER_ROUTED = (AgentRole.INTEGRATION, AgentRole.ADMIN)


@dataclass(frozen=True)
class Advisor:
    """lead-core's projection of an agent: what routing and assignment need.

    Two owners share the row: identity owns everything but `group_id`, which
    lead-core assigns and no identity event carries."""

    agent_id: AgentId
    tenant_id: TenantId
    name: str
    role: AgentRole
    is_active: bool
    version: int
    group_id: Optional[GroupId] = None

    @property
    def id(self) -> AgentId:
        # The name AssignmentEngine reads off every candidate.
        return self.agent_id

    @property
    def is_routable(self) -> bool:
        """A role work can be given to, active or not."""
        return self.role not in _NEVER_ROUTED

    @property
    def is_assignable(self) -> bool:
        return self.is_active and self.is_routable

    def supersedes(self, other: Optional[Advisor]) -> bool:
        # Strictly newer: a redelivered or reordered event must not undo a later change.
        return other is None or self.version > other.version
