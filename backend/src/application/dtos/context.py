from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from domain.entities.agent import Agent


@dataclass(frozen=True)
class RequestContext:
    """Who is acting and on which organization.

    Built once per request from the verified token. Use cases receive it
    instead of a tenant identifier supplied by the caller, which is what makes
    cross-tenant access impossible rather than merely checked."""

    actor: Agent
    tenant_id: Optional[UUID]
