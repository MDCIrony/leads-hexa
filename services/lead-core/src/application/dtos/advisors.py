from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from domain.advisors.advisor import Advisor


@dataclass(frozen=True)
class ListAdvisorsQuery:
    tenant_id: UUID
    group_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class SetAdvisorGroupCommand:
    tenant_id: UUID
    agent_id: UUID
    group_id: Optional[UUID]


@dataclass(frozen=True)
class AdvisorView:
    advisor: Advisor
    active_load: int


@dataclass(frozen=True)
class AdvisorsPage:
    items: List[AdvisorView]
    total: int
