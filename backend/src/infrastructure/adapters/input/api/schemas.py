from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from uuid import UUID
from domain.value_objects.enums import Operator, AssignmentStrategy


def _validate_email_format(value: str) -> str:
    if "@" not in value or "." not in value.split("@")[-1]:
        raise ValueError("Formato de email inválido")
    return value


# --- Lead Schemas ---
class IngestLeadRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email_format(v)

class LeadProcessedResponse(BaseModel):
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    webhook_dispatched: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None

class LeadResponse(BaseModel):
    id: str
    tenant_id: str
    first_name: str
    last_name: str
    email: str
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

class FailedRowResponse(BaseModel):
    row_number: int
    email: str
    error: str
    error_code: Optional[str] = None

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

class ScoringRuleResponse(BaseModel):
    id: str
    name: str
    field: str
    operator: str
    value: Any
    score_delta: int

class RoutingRuleCreate(BaseModel):
    min_score: int
    target_team: str
    assignment_strategy: AssignmentStrategy
    target_agent_ids: List[UUID] = Field(default_factory=list)

class RoutingRuleResponse(BaseModel):
    id: str
    min_score: int
    target_team: str
    assignment_strategy: str
    target_agent_ids: List[str]

# --- Agent Schemas ---
class AgentCreate(BaseModel):
    name: str
    email: str
    team: str
    active_leads_count: int = 0
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email_format(v)

class AgentResponse(BaseModel):
    id: str
    name: str
    email: str
    team: str
    active_leads_count: int
    is_active: bool

class PaginatedAgentsResponse(BaseModel):
    items: List[AgentResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# --- Auth Schemas ---
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
