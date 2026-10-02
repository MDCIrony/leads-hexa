from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from uuid import UUID
from domain.value_objects.enums import (
    AgentMatchMode, Operator, AssignmentStrategy,
)


# --- Lead Schemas ---

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
    # The cursor `?updated_since=` filters on. Without it a consumer catching
    # up has to guess the next cursor from its own clock, and anything
    # committed between its query and the answer falls into the gap.
    updated_at: str

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
    disqualification_reason: Optional[str] = None
    created_at: str

class AgentLoadResponse(BaseModel):
    agent_id: str
    name: str
    active_leads: int

class LeadStatsResponse(BaseModel):
    total: int
    by_status: Dict[str, int]
    unassigned: int
    load_by_agent: List[AgentLoadResponse]

class AssignLeadRequest(BaseModel):
    agent_id: UUID

class DiscardLeadRequest(BaseModel):
    # Empty-means-missing is validated by Lead.discard itself (DISCARD_WITHOUT_REASON),
    # so an omitted field and an explicit "" reach the same domain error.
    reason: str = ""

# --- Rule Schemas ---
class CriterionSchema(BaseModel):
    field: str
    operator: Operator
    # Optional because IS_EMPTY and IS_NOT_EMPTY ask about presence, not value.
    value: Any = None

class ScoringRuleCreate(BaseModel):
    name: str
    conditions: List[CriterionSchema]
    score_delta: int
    priority: int = 0
    is_active: bool = True

class ScoringRuleUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[List[CriterionSchema]] = None
    score_delta: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class ScoringRuleResponse(BaseModel):
    id: str
    name: str
    conditions: List[CriterionSchema]
    score_delta: int
    priority: int
    is_active: bool

class PaginatedScoringRulesResponse(BaseModel):
    items: List[ScoringRuleResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

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
    conditions: List[CriterionSchema] = Field(default_factory=list)

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
    conditions: Optional[List[CriterionSchema]] = None

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
    conditions: List[CriterionSchema]

class PaginatedAssignmentRulesResponse(BaseModel):
    items: List[AssignmentRuleResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Disqualification Rule Schemas ---
class DisqualificationRuleCreate(BaseModel):
    name: str
    conditions: List[CriterionSchema]
    priority: int = 0
    is_active: bool = True

class DisqualificationRuleUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[List[CriterionSchema]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class DisqualificationRuleResponse(BaseModel):
    id: str
    name: str
    conditions: List[CriterionSchema]
    priority: int
    is_active: bool

class PaginatedDisqualificationRulesResponse(BaseModel):
    items: List[DisqualificationRuleResponse]
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

