"""In-memory agent and tenant repositories, with the same versioning rule as the SQL upsert."""
from uuid import UUID

from application.ports.output.agents import AgentRepositoryPort
from application.ports.output.tenants import TenantRepositoryPort
from domain.agents.agent import Agent
from domain.tenants.tenant import Tenant


def _of_tenant(agent: Agent, tenant_id: UUID) -> bool:
    return agent.tenant_id is not None and agent.tenant_id.value == tenant_id


class InMemoryAgentRepository(AgentRepositoryPort):
    def __init__(self) -> None:
        self.agents: dict[UUID, Agent] = {}

    def save(self, agent: Agent) -> Agent:
        # 1 on insert, +1 on every update.
        previous = self.agents.get(agent.id.value)
        agent.version = previous.version + 1 if previous else 1
        self.agents[agent.id.value] = agent
        return agent

    def get_by_id(self, agent_id: UUID) -> Agent | None:
        return self.agents.get(agent_id)

    def get_by_email(self, email: str) -> Agent | None:
        return next((a for a in self.agents.values() if a.email == email), None)

    def count(self) -> int:
        return len(self.agents)

    def _matching(self, tenant_id: UUID, is_active: bool | None) -> list[Agent]:
        return [
            a for a in self.agents.values()
            if _of_tenant(a, tenant_id) and (is_active is None or a.is_active == is_active)
        ]

    def list_by_tenant(
        self, tenant_id: UUID, is_active: bool | None = True, limit: int = 100, offset: int = 0
    ) -> list[Agent]:
        agents = sorted(self._matching(tenant_id, is_active), key=lambda a: (a.name, str(a.id)))
        return agents[offset:offset + limit]

    def count_by_tenant(self, tenant_id: UUID, is_active: bool | None = True) -> int:
        return len(self._matching(tenant_id, is_active))

    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Agent | None:
        agent = self.agents.get(agent_id)
        return agent if agent and _of_tenant(agent, tenant_id) else None

    def deactivate_all_by_tenant(self, tenant_id: UUID) -> list[Agent]:
        affected = self._matching(tenant_id, True)
        for agent in affected:
            agent.is_active = False
            agent.version += 1
        return affected

    def distinct_tenant_ids(self) -> list[UUID]:
        return list({a.tenant_id.value for a in self.agents.values() if a.tenant_id is not None})

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Agent]:
        return sorted(self.agents.values(), key=lambda a: str(a.id))[offset:offset + limit]


class InMemoryTenantRepository(TenantRepositoryPort):
    def __init__(self) -> None:
        self._tenants: dict[UUID, Tenant] = {}
        self._agent_counts: dict[UUID, int] = {}

    def save(self, tenant: Tenant) -> Tenant:
        previous = self._tenants.get(tenant.id.value)
        tenant.version = previous.version + 1 if previous else 1
        self._tenants[tenant.id.value] = tenant
        return tenant

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def get_by_slug(self, slug: str) -> Tenant | None:
        return next((t for t in self._tenants.values() if t.slug == slug), None)

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Tenant]:
        # "ORDER BY created_at DESC, id": two stable sorts keep id ascending as tiebreaker.
        ordered = sorted(self._tenants.values(), key=lambda t: str(t.id))
        ordered.sort(key=lambda t: t.created_at, reverse=True)
        return ordered[offset:offset + limit]

    def count_all(self) -> int:
        return len(self._tenants)

    def count_active_agents(self, tenant_id: UUID) -> int:
        return self._agent_counts.get(tenant_id, 0)

    def set_agent_count(self, tenant_id: UUID, count: int) -> None:
        """Test seam: states the aggregate without wiring an agent repository in."""
        self._agent_counts[tenant_id] = count
