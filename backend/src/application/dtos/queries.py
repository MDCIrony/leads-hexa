from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class GetLeadsQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetAgentsQuery:
    team: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetAgentQuery:
    agent_id: UUID


@dataclass(frozen=True)
class GetRulesQuery:
    tenant_id: UUID


@dataclass(frozen=True)
class GetTenantsQuery:
    limit: int = 100
    offset: int = 0
