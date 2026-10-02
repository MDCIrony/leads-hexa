from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from domain.value_objects.agent_role import AgentRole


@dataclass(frozen=True)
class Principal:
    """Who is acting, exactly as the verified token states it. Shaped as the policy's
    Actor (id, tenant_id, role) so AuthorizationPolicy takes it unchanged."""

    id: UUID
    tenant_id: UUID | None
    role: AgentRole
    principal_type: Literal["human", "integration"]


@dataclass(frozen=True)
class RequestContext:
    """Who is acting and on which organization, built once per request from the token:
    use cases never receive a tenant the caller chose."""

    principal: Principal
    tenant_id: UUID | None
