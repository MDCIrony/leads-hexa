from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class GetLeadsQuery:
    tenant_id: UUID
    status: Optional[str] = None
    assigned_agent_id: Optional[UUID] = None
    group_id: Optional[UUID] = None
    source_id: Optional[UUID] = None
    search: Optional[str] = None
    # What changed since an instant. A consumer that was away — or that lost
    # messages — asks for the window instead of paging the organization.
    updated_since: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetRulesQuery:
    tenant_id: UUID
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
class GetDisqualificationRulesQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetMyLeadsQuery:
    tenant_id: UUID
    agent_id: UUID
    status: Optional[str] = None
    search: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetLeadQuery:
    tenant_id: UUID
    lead_id: UUID


@dataclass(frozen=True)
class GetLeadStatsQuery:
    tenant_id: UUID
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
