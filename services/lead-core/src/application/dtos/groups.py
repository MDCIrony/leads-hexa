from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID


if TYPE_CHECKING:
    from domain.groups.sales_group import SalesGroup



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
class GetSalesGroupsQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class SalesGroupSummary:
    group: "SalesGroup"
    agent_count: int


@dataclass(frozen=True)
class SalesGroupsPageResult:
    items: List[SalesGroupSummary]
    total: int
