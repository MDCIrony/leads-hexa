from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from domain.value_objects.agent_id import AgentId


@dataclass
class Agent:
    id: AgentId
    name: str
    email: str
    team: str
    active_leads_count: int = 0
    is_active: bool = True

    @classmethod
    def create(
        cls,
        name: str,
        email: str,
        team: str,
        active_leads_count: int = 0,
        is_active: bool = True,
        agent_id: Optional[Union[str, UUID, AgentId]] = None,
    ) -> "Agent":
        aid = agent_id if isinstance(agent_id, AgentId) else AgentId(agent_id)
        return cls(
            id=aid,
            name=name,
            email=email,
            team=team,
            active_leads_count=active_leads_count,
            is_active=is_active,
        )

