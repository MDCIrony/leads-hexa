from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

if TYPE_CHECKING:
    from domain.entities.agent import Agent
    from domain.entities.lead import Lead


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
    team: str
    password: str
    active_leads_count: int = 0
    is_active: bool = True
    role: str = "AGENT"
    tenant_id: Optional[UUID] = None


@dataclass(frozen=True)
class CreateScoringRuleCommand:
    tenant_id: UUID
    name: str
    field: str
    operator: str
    value: str
    score_delta: int


@dataclass(frozen=True)
class CreateRoutingRuleCommand:
    tenant_id: UUID
    min_score: int
    target_team: str
    assignment_strategy: str
    target_agent_ids: List[UUID]


@dataclass(frozen=True)
class FailedRow:
    row_number: int
    email: str
    error: str
    error_code: str


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
class BatchProcessResult:
    job_id: str
    total_rows: int
    successful_ingestions: int
    failed_rows: List[FailedRow]
