from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID


if TYPE_CHECKING:
    from domain.leads.lead import Lead



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


@dataclass(frozen=True)
class LeadsPageResult:
    items: List["Lead"]
    total: int


@dataclass(frozen=True)
class AssignLeadCommand:
    tenant_id: UUID
    lead_id: UUID
    agent_id: UUID


@dataclass(frozen=True)
class DiscardLeadCommand:
    tenant_id: UUID
    lead_id: UUID
    reason: str


@dataclass(frozen=True)
class AgentLoad:
    agent_id: UUID
    name: str
    active_leads: int


@dataclass(frozen=True)
class LeadStatsResult:
    total: int
    by_status: Dict[str, int]
    unassigned: int
    load_by_agent: List[AgentLoad]
