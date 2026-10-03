from typing import List, Optional

from pydantic import BaseModel

from domain.value_objects.enums import AssignmentStrategy


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
