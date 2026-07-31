from dataclasses import dataclass
from domain.value_objects.agent_id import AgentId

@dataclass
class Agent:
    id: AgentId
    name: str
    email: str
    team: str
    active_leads_count: int = 0
    is_active: bool = True
