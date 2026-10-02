from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdvisorGroupUpdate(BaseModel):
    # Required though nullable: an empty body must not read as "remove the group".
    model_config = ConfigDict(extra="forbid")
    group_id: Optional[UUID]


class AdvisorResponse(BaseModel):
    agent_id: str
    name: str
    group_id: Optional[str]
    is_active: bool
    active_load: int


class AdvisorsPageResponse(BaseModel):
    items: List[AdvisorResponse]
    total: int
    limit: int
    offset: int
