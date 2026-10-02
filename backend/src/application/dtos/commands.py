from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

if TYPE_CHECKING:
    from domain.entities.disqualification_rule import DisqualificationRule
    from domain.entities.lead import Lead
    from domain.entities.rule import ScoringRule
    from domain.entities.sales_group import SalesGroup


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
    # Every field below is None-means-unchanged (same
    # convention as the rule updates). That makes capacity_per_agent unable to be
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
