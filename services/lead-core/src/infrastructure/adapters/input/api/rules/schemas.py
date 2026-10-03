from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy, Operator


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
