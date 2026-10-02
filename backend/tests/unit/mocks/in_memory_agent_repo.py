from typing import List, Optional, Dict
from uuid import UUID
from application.ports.output.agent_repository_port import AgentRepositoryPort
from domain.entities.agent import Agent

class InMemoryAgentRepository(AgentRepositoryPort):
    def __init__(self) -> None:
        self.agents: Dict[UUID, Agent] = {}

    def _filter_by_group(self, agents: List[Agent], group_id: Optional[UUID]) -> List[Agent]:
        if not group_id:
            return agents
        return [a for a in agents if a.group_id and a.group_id.value == group_id]

    def get_available_agents(self, tenant_id: UUID, group_id: Optional[UUID] = None) -> List[Agent]:
        agents = [
            a
            for a in self.agents.values()
            if a.is_active and a.tenant_id is not None and a.tenant_id.value == tenant_id
        ]
        return self._filter_by_group(agents, group_id)

    def save(self, agent: Agent) -> Agent:
        # Same rule as the SQL upsert: 1 on insert, +1 on every update.
        previous = self.agents.get(agent.id.value)
        agent.version = previous.version + 1 if previous else 1
        self.agents[agent.id.value] = agent
        return agent

    def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def list_active(self, group_id: Optional[UUID] = None, limit: int = 100, offset: int = 0) -> List[Agent]:
        agents = [a for a in self.agents.values() if a.is_active]
        agents = self._filter_by_group(agents, group_id)
        return agents[offset:offset + limit]

    def count_active(self, group_id: Optional[UUID] = None) -> int:
        agents = [a for a in self.agents.values() if a.is_active]
        return len(self._filter_by_group(agents, group_id))

    def get_by_email(self, email: str) -> Optional[Agent]:
        return next((a for a in self.agents.values() if a.email.lower() == email.lower()), None)

    def count(self) -> int:
        return len(self.agents)

    def _filter_by_active(self, agents: List[Agent], is_active: Optional[bool]) -> List[Agent]:
        if is_active is None:
            return agents
        return [a for a in agents if a.is_active == is_active]

    def list_by_tenant(
        self,
        tenant_id: UUID,
        group_id: Optional[UUID] = None,
        is_active: Optional[bool] = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Agent]:
        agents = [
            a for a in self.agents.values() if a.tenant_id is not None and a.tenant_id.value == tenant_id
        ]
        agents = self._filter_by_active(agents, is_active)
        agents = self._filter_by_group(agents, group_id)
        agents.sort(key=lambda a: (a.name, str(a.id)))
        return agents[offset : offset + limit]

    def count_by_tenant(
        self, tenant_id: UUID, group_id: Optional[UUID] = None, is_active: Optional[bool] = True
    ) -> int:
        agents = [
            a for a in self.agents.values() if a.tenant_id is not None and a.tenant_id.value == tenant_id
        ]
        agents = self._filter_by_active(agents, is_active)
        return len(self._filter_by_group(agents, group_id))

    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]:
        agent = self.agents.get(agent_id)
        if agent is None or agent.tenant_id is None or agent.tenant_id.value != tenant_id:
            return None
        return agent

    def deactivate_all_by_tenant(self, tenant_id: UUID) -> List[Agent]:
        affected = [
            a
            for a in self.agents.values()
            if a.is_active and a.tenant_id is not None and a.tenant_id.value == tenant_id
        ]
        for agent in affected:
            agent.is_active = False
            agent.version += 1
        return affected

    def distinct_tenant_ids(self) -> List[UUID]:
        return list({a.tenant_id.value for a in self.agents.values() if a.tenant_id is not None})
