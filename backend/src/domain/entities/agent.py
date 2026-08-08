from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from domain.value_objects.agent_id import AgentId
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId
from domain.value_objects.enums import AgentRole


@dataclass
class Agent:
    id: AgentId
    name: str
    email: str
    group_id: Optional[GroupId] = None
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
        group_id: Optional[Union[str, UUID, GroupId]] = None,
        active_leads_count: int = 0,
        is_active: bool = True,
        agent_id: Optional[Union[str, UUID, AgentId]] = None,
        role: Union[str, AgentRole] = AgentRole.AGENT,
        hashed_password: Optional[str] = None,
        tenant_id: Optional[Union[str, UUID, TenantId]] = None,
    ) -> "Agent":
        aid = agent_id if isinstance(agent_id, AgentId) else AgentId(agent_id)
        agent_role = role if isinstance(role, AgentRole) else AgentRole(role)
        gid: Optional[GroupId]
        if group_id is None:
            gid = None
        elif isinstance(group_id, GroupId):
            gid = group_id
        else:
            gid = GroupId(group_id)
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
            group_id=gid,
            active_leads_count=active_leads_count,
            is_active=is_active,
            role=agent_role,
            hashed_password=hashed_password,
            tenant_id=tid,
        )

