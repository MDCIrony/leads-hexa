from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    """Who is acting, exactly as the verified token states it. No profile data:
    a service that needs a name or an email asks the owner of that data."""

    agent_id: UUID
    tenant_id: UUID | None
    role: str
    principal_type: Literal["human", "integration"]


@dataclass(frozen=True)
class RequestContext:
    """Who is acting and on which organization, built once per request from the verified token."""

    principal: Principal
    tenant_id: UUID | None
