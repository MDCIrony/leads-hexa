from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from domain.value_objects.agent_id import AgentId
from domain.value_objects.tenant_id import TenantId
from domain.value_objects.enums import AgentRole


@dataclass
class Agent:
    id: AgentId
    name: str
    email: str
    team: str
    active_leads_count: int = 0
    is_active: bool = True
    role: AgentRole = AgentRole.AGENT
    hashed_password: Optional[str] = None
    tenant_id: Optional[TenantId] = None

    @classmethod
    def create(
        cls,
        name: str,
        email: str,
        team: str,
        active_leads_count: int = 0,
        is_active: bool = True,
        agent_id: Optional[Union[str, UUID, AgentId]] = None,
        role: Union[str, AgentRole] = AgentRole.AGENT,
        hashed_password: Optional[str] = None,
        tenant_id: Optional[Union[str, UUID, TenantId]] = None,
    ) -> "Agent":
        aid = agent_id if isinstance(agent_id, AgentId) else AgentId(agent_id)
        agent_role = role if isinstance(role, AgentRole) else AgentRole(role)
        tid: Optional[TenantId]
        if tenant_id is None:
            tid = None
        elif isinstance(tenant_id, TenantId):
            tid = tenant_id
        else:
            tid = TenantId(tenant_id)
        return cls(
            id=aid,
            name=name,
            email=email,
            team=team,
            active_leads_count=active_leads_count,
            is_active=is_active,
            role=agent_role,
            hashed_password=hashed_password,
            tenant_id=tid,
        )

