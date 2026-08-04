from typing import Optional
from pydantic import BaseModel
from uuid import UUID

class GetLeadsQuery(BaseModel):
    tenant_id: UUID
    limit: int = 100
    offset: int = 0

class GetAgentsQuery(BaseModel):
    team: Optional[str] = None
    limit: int = 100
    offset: int = 0

class GetAgentQuery(BaseModel):
    agent_id: UUID

class GetRulesQuery(BaseModel):
    tenant_id: UUID
