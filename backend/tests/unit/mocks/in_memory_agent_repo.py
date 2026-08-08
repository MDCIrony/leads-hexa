from typing import List, Optional, Dict
from uuid import UUID
from application.ports.output.agent_repository_port import AgentRepositoryPort
from domain.entities.agent import Agent

class InMemoryAgentRepository(AgentRepositoryPort):
    def __init__(self) -> None:
        self.agents: Dict[UUID, Agent] = {}

    def get_available_agents(self, team: Optional[str] = None) -> List[Agent]:
        agents = [a for a in self.agents.values() if a.is_active]
        if team:
            agents = [a for a in agents if a.team == team]
        return agents

    def update_active_count(self, agent_id: UUID, new_count: int) -> None:
        if agent_id in self.agents:
            self.agents[agent_id].active_leads_count = new_count

    def save(self, agent: Agent) -> Agent:
        self.agents[agent.id.value] = agent
        return agent

    def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def list_active(self, team: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Agent]:
        agents = [a for a in self.agents.values() if a.is_active]
        if team:
            agents = [a for a in agents if a.team == team]
        return agents[offset:offset + limit]

    def count_active(self, team: Optional[str] = None) -> int:
        agents = [a for a in self.agents.values() if a.is_active]
        if team:
            agents = [a for a in agents if a.team == team]
        return len(agents)

    def get_by_email(self, email: str) -> Optional[Agent]:
        return next((a for a in self.agents.values() if a.email == email), None)

    def count(self) -> int:
        return len(self.agents)

    def list_by_tenant(
        self, tenant_id: UUID, team: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Agent]:
        agents = [
            a
            for a in self.agents.values()
            if a.is_active and a.tenant_id is not None and a.tenant_id.value == tenant_id
        ]
        if team:
            agents = [a for a in agents if a.team == team]
        agents.sort(key=lambda a: (a.name, str(a.id)))
        return agents[offset : offset + limit]

    def count_by_tenant(self, tenant_id: UUID, team: Optional[str] = None) -> int:
        agents = [
            a
            for a in self.agents.values()
            if a.is_active and a.tenant_id is not None and a.tenant_id.value == tenant_id
        ]
        if team:
            agents = [a for a in agents if a.team == team]
        return len(agents)

    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]:
        agent = self.agents.get(agent_id)
        if agent is None or agent.tenant_id is None or agent.tenant_id.value != tenant_id:
            return None
        return agent

    def distinct_tenant_ids(self) -> List[UUID]:
        return list({a.tenant_id.value for a in self.agents.values() if a.tenant_id is not None})
