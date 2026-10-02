from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

MANAGER_ROLE = "MANAGER"


@dataclass(frozen=True)
class Member:
    """Local projection of an agent: just what deciding who gets a notice needs.

    The owner of the agent data is the identity service; this copy is rebuilt
    from its events."""

    agent_id: UUID
    tenant_id: UUID
    role: str
    is_active: bool
    version: int

    @property
    def receives_organization_notices(self) -> bool:
        return self.role == MANAGER_ROLE and self.is_active

    def supersedes(self, other: Member | None) -> bool:
        # Strictly newer: a redelivered or reordered event must not undo a later change.
        return other is None or self.version > other.version
