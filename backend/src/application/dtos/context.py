from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from domain.value_objects.enums import AgentRole


@dataclass(frozen=True)
class Principal:
    """Who is acting, exactly as the verified token states it. No profile data:
    a service that needs a name or an email asks the owner of that data."""

    id: UUID
    tenant_id: Optional[UUID]
    role: AgentRole
    principal_type: str  # "human" | "integration"


@dataclass(frozen=True)
class RequestContext:
    """Who is acting and on which organization.

    Built once per request from the verified token. Use cases receive it
    instead of a tenant identifier supplied by the caller, which is what makes
    cross-tenant access impossible rather than merely checked."""

    principal: Principal
    tenant_id: Optional[UUID]
