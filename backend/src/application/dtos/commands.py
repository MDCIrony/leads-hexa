from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

if TYPE_CHECKING:
    from domain.entities.agent import Agent
    from domain.entities.disqualification_rule import DisqualificationRule
    from domain.entities.intake_job import IntakeJob
    from domain.entities.intake_record import IntakeRecord
    from domain.entities.lead import Lead
    from domain.entities.lead_source import LeadSource
    from domain.entities.rule import ScoringRule
    from domain.entities.sales_group import SalesGroup
    from domain.entities.tenant import Tenant


@dataclass(frozen=True)
class IngestLeadCommand:
    tenant_id: UUID
    source_id: UUID
    first_name: str
    last_name: str
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    phone: Optional[str] = None
    email: Optional[str] = None


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
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class CreateScoringRuleCommand:
    tenant_id: UUID
    name: str
    # Plain dicts, not Criterion: the DTO stays a transport shape and the use
    # case is where it becomes a domain object.
    conditions: List[Dict[str, Any]]
    score_delta: int
    priority: int = 0
    is_active: bool = True


@dataclass(frozen=True)
class UpdateScoringRuleCommand:
    tenant_id: UUID
    rule_id: UUID
    # None-means-unchanged, same convention as UpdateDisqualificationRuleCommand.
    name: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    score_delta: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class ScoringRulesPageResult:
    items: List["ScoringRule"]
    total: int


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
    # Plain dicts, not Criterion: same convention as CreateScoringRuleCommand.
    conditions: List[Dict[str, Any]] = field(default_factory=list)


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
    conditions: Optional[List[Dict[str, Any]]] = None


@dataclass(frozen=True)
class CreateDisqualificationRuleCommand:
    tenant_id: UUID
    name: str
    # Plain dicts, not Criterion: same convention as CreateScoringRuleCommand.
    conditions: List[Dict[str, Any]]
    priority: int = 0
    is_active: bool = True


@dataclass(frozen=True)
class UpdateDisqualificationRuleCommand:
    tenant_id: UUID
    rule_id: UUID
    # None-means-unchanged, same convention as every other PATCH command here.
    name: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class DisqualificationRulesPageResult:
    items: List["DisqualificationRule"]
    total: int


@dataclass(frozen=True)
class FailedRow:
    row_number: int
    # Optional since T2: a lead without an email is valid, and a row can
    # still fail for another reason (e.g. a bad budget) while missing one.
    email: Optional[str]
    error: str
    # A row can fail without a domain error code — an unexpected parse failure
    # carries a message but no stable code for the client to branch on.
    error_code: Optional[str] = None
    # What the failure is recoverable from: the manager fixes the payload
    # sitting in this IntakeRecord instead of re-submitting the whole row.
    intake_record_id: str = ""


@dataclass(frozen=True)
class LeadProcessedResult:
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None
    # Always populated, success or rejection: the link from a result back to
    # the payload that produced it.
    intake_record_id: str = ""


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
class AgentsPageResult:
    items: List["Agent"]
    total: int


@dataclass(frozen=True)
class IssueIntegrationCredentialCommand:
    tenant_id: UUID


@dataclass(frozen=True)
class IntegrationCredentialResult:
    agent: "Agent"
    api_key: str
    kafka_username: str
    kafka_password: str
    kafka_topic: str


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


@dataclass(frozen=True)
class CreateLeadSourceCommand:
    tenant_id: UUID
    name: str
    kind: str
    field_mapping: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class UpdateLeadSourceCommand:
    tenant_id: UUID
    source_id: UUID
    # None-means-unchanged, same convention as UpdateSalesGroupCommand.
    name: Optional[str] = None
    field_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class LeadSourcesPageResult:
    items: List["LeadSource"]
    total: int


@dataclass(frozen=True)
class PromoteIntakeRecordCommand:
    tenant_id: UUID
    record_id: UUID
    # The full corrected payload, not a patch: the manager resends the whole
    # form from the inbox.
    payload: Dict[str, Any]


@dataclass(frozen=True)
class IntakeRecordsPageResult:
    items: List["IntakeRecord"]
    total: int


@dataclass(frozen=True)
class ReceiveIntakeCommand:
    tenant_id: UUID
    kind: str  # IntakeJobKind as str: DTOs do not import domain enums
    # A list, not a dict: unit intake sends one payload and bulk intake sends
    # none yet, because the file is parsed in phase 2.
    payloads: List[Dict[str, Any]]
    # The uploaded file of a batch, kept as received; parsing is the worker's.
    filename: Optional[str] = None
    content: Optional[bytes] = None


@dataclass(frozen=True)
class ReceiveIntakeResult:
    job_id: str
    record_ids: List[str]
    status: str


@dataclass(frozen=True)
class IntakeJobsPageResult:
    items: List["IntakeJob"]
    total: int


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
    pending_intake: int
    load_by_agent: List[AgentLoad]


@dataclass(frozen=True)
class OutboxEntry:
    """One row of the transactional outbox, read back for delivery.

    Delivery mechanics, not a domain concept — the outbox doesn't know what
    a lead is, only that this payload needs to reach a transport."""

    id: UUID
    # None for state with no organization, e.g. the platform admin's identity.
    tenant_id: Optional[str]
    partition_key: str
    event_type: str
    payload: Dict[str, Any]
    occurred_on: datetime
    channel: str = "product"
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class StoredIntakeFile:
    """An uploaded file as received, kept before anything parses it."""

    job_id: UUID
    tenant_id: UUID
    filename: str
    content: bytes
    parsed_at: Optional[datetime] = None
