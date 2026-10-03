from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


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
