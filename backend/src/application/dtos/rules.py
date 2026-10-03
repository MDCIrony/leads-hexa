from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID


if TYPE_CHECKING:
    from domain.rules.disqualification_rule import DisqualificationRule
    from domain.rules.scoring_rule import ScoringRule



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
class GetRulesQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class ScoringRulesPageResult:
    items: List["ScoringRule"]
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
class GetAssignmentRulesQuery:
    tenant_id: UUID


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
class GetDisqualificationRulesQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class DisqualificationRulesPageResult:
    items: List["DisqualificationRule"]
    total: int
