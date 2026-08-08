from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

if TYPE_CHECKING:
    from domain.entities.agent import Agent
    from domain.entities.lead import Lead
    from domain.entities.sales_group import SalesGroup
    from domain.entities.tenant import Tenant


@dataclass(frozen=True)
class IngestLeadCommand:
    tenant_id: UUID
    first_name: str
    last_name: str
    email: str
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    phone: Optional[str] = None


@dataclass(frozen=True)
class CreateAgentCommand:
    name: str
    email: str
    password: str
    group_id: Optional[UUID] = None
    is_active: bool = True
    role: str = "AGENT"
    tenant_id: Optional[UUID] = None


@dataclass(frozen=True)
class UpdateAgentCommand:
    tenant_id: UUID
    agent_id: UUID
    name: Optional[str] = None
    # None means "leave unchanged", matching every other PATCH command in
    # this module; clearing an agent's group entirely is not a use case any
    # brief asks for yet.
    group_id: Optional[UUID] = None


@dataclass(frozen=True)
class CreateScoringRuleCommand:
    tenant_id: UUID
    name: str
    field: str
    operator: str
    # Any, not str: coercing here is what kept the IN operator from ever
    # matching, since the engine needs the list the manager actually sent.
    value: Any
    score_delta: int
    priority: int = 0
    is_active: bool = True


@dataclass(frozen=True)
class CreateSalesGroupCommand:
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    default_strategy: str = "LOWEST_LOAD"
    capacity_per_agent: Optional[int] = None


@dataclass(frozen=True)
class UpdateSalesGroupCommand:
    tenant_id: UUID
    group_id: UUID
    # Every field below is None-means-unchanged (same convention as
    # UpdateTenantCommand). That makes capacity_per_agent unable to be
    # PATCHed back to "uncapped" without a sentinel value; no brief exercises
    # that case, so it is not worth the extra machinery yet.
    name: Optional[str] = None
    description: Optional[str] = None
    default_strategy: Optional[str] = None
    capacity_per_agent: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class SalesGroupSummary:
    group: "SalesGroup"
    agent_count: int


@dataclass(frozen=True)
class SalesGroupsPageResult:
    items: List[SalesGroupSummary]
    total: int


@dataclass(frozen=True)
class CreateAssignmentRuleCommand:
    tenant_id: UUID
    name: str
    min_score: int = 0
    max_score: Optional[int] = None
    target_group_id: Optional[UUID] = None
    target_agent_ids: List[UUID] = field(default_factory=list)
    agent_match_mode: str = "ANY"
    strategy: Optional[str] = None
    priority: int = 0


@dataclass(frozen=True)
class UpdateAssignmentRuleCommand:
    tenant_id: UUID
    rule_id: UUID
    # None-means-unchanged throughout, as elsewhere; rr_cursor is
    # deliberately absent so a partial update can never reset a rotation
    # already in progress.
    name: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    target_group_id: Optional[UUID] = None
    target_agent_ids: Optional[List[UUID]] = None
    agent_match_mode: Optional[str] = None
    strategy: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class FailedRow:
    row_number: int
    email: str
    error: str
    # A row can fail without a domain error code — an unexpected parse failure
    # carries a message but no stable code for the client to branch on.
    error_code: Optional[str] = None


@dataclass(frozen=True)
class LeadProcessedResult:
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    webhook_dispatched: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass(frozen=True)
class LeadsPageResult:
    items: List["Lead"]
    total: int


@dataclass(frozen=True)
class AgentsPageResult:
    items: List["Agent"]
    total: int


@dataclass(frozen=True)
class CreateTenantCommand:
    name: str
    manager_name: str
    manager_email: str
    manager_password: str


@dataclass(frozen=True)
class UpdateTenantCommand:
    tenant_id: UUID
    name: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class TenantWithManagerResult:
    tenant: "Tenant"
    manager: "Agent"


@dataclass(frozen=True)
class TenantSummary:
    tenant: "Tenant"
    agent_count: int


@dataclass(frozen=True)
class TenantsPageResult:
    items: List[TenantSummary]
    total: int


@dataclass(frozen=True)
class BatchProcessResult:
    job_id: str
    total_rows: int
    successful_ingestions: int
    failed_rows: List[FailedRow]
