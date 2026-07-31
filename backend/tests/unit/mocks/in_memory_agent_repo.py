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
