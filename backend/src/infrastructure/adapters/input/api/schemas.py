from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from domain.value_objects.enums import (
    AgentMatchMode, Operator, AssignmentStrategy, AgentRole, LeadSourceKind,
)


def _validate_email_format(value: str) -> str:
    if "@" not in value or "." not in value.split("@")[-1]:
        raise ValueError("Formato de email inválido")
    return value


# --- Lead Schemas ---
class IngestLeadRequest(BaseModel):
    # V1: no format validation here on purpose. It used to duplicate
    # EmailAddress with a looser rule and produce a 422 that discarded the
    # payload before anything was persisted — a malformed email now reaches
    # the domain, which rejects it while keeping the record in the tray.
    first_name: str
    last_name: str
    email: Optional[str] = None
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)
    phone: Optional[str] = None

class IntakeAcceptedResponse(BaseModel):
    job_id: str
    record_ids: List[str]
    status: str

class LeadProcessedResponse(BaseModel):
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    webhook_dispatched: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None
    # The payload this lead came from. Answers "what did the client actually
    # send?" for a lead whose data looks wrong after the fact.
    intake_record_id: str = ""

class LeadResponse(BaseModel):
    id: str
    tenant_id: str
    source_id: str
    first_name: str
    last_name: str
    email: Optional[str]
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any]
    phone: Optional[str]
    score: int
    status: str
    assigned_agent_id: Optional[str]
    created_at: str

class PaginatedLeadsResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

class AppliedRuleResponse(BaseModel):
    rule_id: str
    name: str
    score_delta: int

class LeadDetailResponse(BaseModel):
    id: str
    tenant_id: str
    source_id: str
    first_name: str
    last_name: str
    email: Optional[str]
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any]
    phone: Optional[str]
    score: int
    score_breakdown: List[AppliedRuleResponse]
    status: str
    assigned_agent_id: Optional[str]
    assigned_at: Optional[str]
    discard_reason: Optional[str]
    created_at: str

class AssignLeadRequest(BaseModel):
    agent_id: UUID

class DiscardLeadRequest(BaseModel):
    # Empty-means-missing is validated by Lead.discard itself (DISCARD_WITHOUT_REASON),
    # so an omitted field and an explicit "" reach the same domain error.
    reason: str = ""

class FailedRowResponse(BaseModel):
    row_number: int
    # Optional since T2: a missing email is valid data, not a parse failure,
    # and a row can fail for an unrelated reason while missing one. A bare
    # `str` here raised pydantic.ValidationError on such a row, turning a
    # legitimate partial-success batch response into an HTTP 500.
    email: Optional[str] = None
    error: str
    error_code: Optional[str] = None
    # Without this the manager can see WHICH rows failed but not WHERE they
    # were stored, and has to pair a 500-row upload against the inbox by
    # matching contents — ambiguous the moment two rows look alike.
    intake_record_id: str = ""

class BatchProcessResponse(BaseModel):
    job_id: str
    total_rows: int
    successful_ingestions: int
    failed_rows: List[FailedRowResponse]

# --- Rule Schemas ---
class ScoringRuleCreate(BaseModel):
    name: str
    field: str
    operator: Operator
    value: Any
    score_delta: int
    priority: int = 0
    is_active: bool = True

class ScoringRuleResponse(BaseModel):
    id: str
    name: str
    field: str
    operator: str
    value: Any
    score_delta: int
    priority: int
    is_active: bool

# --- Assignment Rule Schemas ---
class AssignmentRuleCreate(BaseModel):
    name: str
    min_score: int = 0
    max_score: Optional[int] = None
    target_group_id: Optional[UUID] = None
    target_agent_ids: List[UUID] = Field(default_factory=list)
    agent_match_mode: AgentMatchMode = AgentMatchMode.ANY
    strategy: Optional[AssignmentStrategy] = None
    priority: int = 0

class AssignmentRuleUpdate(BaseModel):
    name: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    target_group_id: Optional[UUID] = None
    target_agent_ids: Optional[List[UUID]] = None
    agent_match_mode: Optional[AgentMatchMode] = None
    strategy: Optional[AssignmentStrategy] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class AssignmentRuleResponse(BaseModel):
    id: str
    name: str
    min_score: int
    max_score: Optional[int] = None
    target_group_id: Optional[str] = None
    target_agent_ids: List[str]
    agent_match_mode: str
    strategy: Optional[str] = None
    priority: int
    is_active: bool
    rr_cursor: int

class PaginatedAssignmentRulesResponse(BaseModel):
    items: List[AssignmentRuleResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Sales Group Schemas ---
class SalesGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    default_strategy: AssignmentStrategy = AssignmentStrategy.LOWEST_LOAD
    capacity_per_agent: Optional[int] = None

class SalesGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_strategy: Optional[AssignmentStrategy] = None
    capacity_per_agent: Optional[int] = None
    is_active: Optional[bool] = None

class SalesGroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    default_strategy: str
    capacity_per_agent: Optional[int] = None
    is_active: bool
    # Absent (None) on a create response, populated on a list response —
    # same convention as TenantResponse.agent_count.
    agent_count: Optional[int] = None

class PaginatedGroupsResponse(BaseModel):
    items: List[SalesGroupResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Lead Source Schemas ---
class LeadSourceCreate(BaseModel):
    name: str
    kind: LeadSourceKind
    field_mapping: Optional[Dict[str, str]] = None

class LeadSourceUpdate(BaseModel):
    name: Optional[str] = None
    field_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None

class LeadSourceResponse(BaseModel):
    id: str
    name: str
    kind: str
    field_mapping: Dict[str, str]
    is_active: bool
    created_at: datetime

class PaginatedSourcesResponse(BaseModel):
    items: List[LeadSourceResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Agent Schemas ---
class AgentCreate(BaseModel):
    name: str
    email: str
    group_id: Optional[UUID] = None
    is_active: bool = True
    password: str
    role: AgentRole = AgentRole.AGENT
    # No tenant_id: the organization is always the caller's own, taken from
    # the authenticated context, never from the request body.

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email_format(v)

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    group_id: Optional[UUID] = None

class AgentResponse(BaseModel):
    id: str
    name: str
    email: str
    group_id: Optional[str] = None
    is_active: bool
    role: str
    tenant_id: Optional[str] = None

class PaginatedAgentsResponse(BaseModel):
    items: List[AgentResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Tenant Schemas ---
class TenantManagerCreate(BaseModel):
    name: str
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email_format(v)

class TenantCreate(BaseModel):
    name: str
    manager: TenantManagerCreate

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    created_at: str
    # Both are absent on some responses by design: the list view aggregates
    # a count without identities (no manager), the create view has no
    # meaningful count yet for a just-created organization.
    agent_count: Optional[int] = None
    manager: Optional[AgentResponse] = None

class PaginatedTenantsResponse(BaseModel):
    items: List[TenantResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Intake Record Schemas ---
class IntakeErrorResponse(BaseModel):
    field: str
    message: str
    received_value: Optional[str] = None
    error_code: Optional[str] = None

class IntakeRecordResponse(BaseModel):
    id: str
    source_id: str
    status: str
    payload: Dict[str, Any]
    errors: List[IntakeErrorResponse]
    received_at: datetime
    processed_at: Optional[datetime] = None
    lead_id: Optional[str] = None

class IntakeRecordsPageResponse(BaseModel):
    items: List[IntakeRecordResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

class PromoteIntakeRecordRequest(BaseModel):
    payload: Dict[str, Any]

class IntakeJobResponse(BaseModel):
    id: str
    source_id: str
    kind: str
    status: str
    # Null until the file is parsed: in a batch upload the total is not known
    # when the request is accepted.
    total_items: Optional[int] = None
    succeeded: int
    failed: int
    created_at: datetime
    completed_at: Optional[datetime] = None

class IntakeJobsPageResponse(BaseModel):
    items: List[IntakeJobResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Auth Schemas ---
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class CurrentUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
