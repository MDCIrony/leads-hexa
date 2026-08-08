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
    tenant_id: UUID
    group_id: Optional[UUID] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetAgentQuery:
    tenant_id: UUID
    agent_id: UUID


@dataclass(frozen=True)
class GetRulesQuery:
    tenant_id: UUID


@dataclass(frozen=True)
class GetTenantsQuery:
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetSalesGroupsQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetAssignmentRulesQuery:
    tenant_id: UUID


@dataclass(frozen=True)
class GetMyLeadsQuery:
    tenant_id: UUID
    agent_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetLeadQuery:
    tenant_id: UUID
    lead_id: UUID


@dataclass(frozen=True)
class GetLeadSourcesQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetIntakeRecordsQuery:
    tenant_id: UUID
    status: Optional[str] = None
    job_id: Optional[UUID] = None
    limit: int = 100
    offset: int = 0
