from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from domain.value_objects.agent_id import AgentId
from domain.value_objects.agent_role import AgentRole
from domain.value_objects.tenant_id import TenantId


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass
class Agent:
    """A person or machine that signs in to an organization, or the platform admin.

    No sales group: grouping belongs to the leads side, which keeps it in its
    own projection of this agent."""

    id: AgentId
    name: str
    email: str
    is_active: bool = True
    role: AgentRole = AgentRole.AGENT
    hashed_password: Optional[str] = None
    tenant_id: Optional[TenantId] = None
    # Assigned by the database on every write; see AgentRepositoryPort.save.
    version: int = 1

    @classmethod
    def create(
        cls,
        name: str,
        email: str,
        # Keyword-only: the slot after email used to be group_id, and a
        # leftover positional call must fail instead of landing in is_active.
        *,
        is_active: bool = True,
        agent_id: Optional[Union[str, UUID, AgentId]] = None,
        role: Union[str, AgentRole] = AgentRole.AGENT,
        hashed_password: Optional[str] = None,
        tenant_id: Optional[Union[str, UUID, TenantId]] = None,
        version: int = 1,
    ) -> "Agent":
        tid: Optional[TenantId]
        if tenant_id is None or isinstance(tenant_id, TenantId):
            tid = tenant_id
        else:
            tid = TenantId(tenant_id)
        return cls(
            id=agent_id if isinstance(agent_id, AgentId) else AgentId(agent_id),
            name=name,
            email=normalize_email(email),
            is_active=is_active,
            role=role if isinstance(role, AgentRole) else AgentRole(role),
            hashed_password=hashed_password,
            tenant_id=tid,
            version=version,
        )
