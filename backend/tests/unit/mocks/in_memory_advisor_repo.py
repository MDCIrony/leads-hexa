from dataclasses import replace
from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.advisors.advisor_repository_port import AdvisorRepositoryPort
from domain.advisors.advisor import Advisor
from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from domain.value_objects.group_id import GroupId


def advisor_of(agent: Agent) -> Advisor:
    """The advisor the projection holds for `agent`, group included."""
    return Advisor(agent.id, agent.tenant_id, agent.name, agent.role, agent.is_active, agent.version, agent.group_id)


class InMemoryAdvisorRepository(AdvisorRepositoryPort):
    def __init__(self) -> None:
        self.advisors: Dict[UUID, Advisor] = {}

    def seed(self, advisor: Advisor) -> Advisor:
        """Stores the row as given, group included, like the migration's seed."""
        self.advisors[advisor.agent_id.value] = advisor
        return advisor

    def _routable(self, tenant_id: UUID, group_id: Optional[UUID]) -> List[Advisor]:
        found = [
            a for a in self.advisors.values()
            if a.tenant_id.value == tenant_id and a.role != AgentRole.INTEGRATION
            and (group_id is None or (a.group_id is not None and a.group_id.value == group_id))
        ]
        return sorted(found, key=lambda a: (a.name, str(a.agent_id)))

    def get(self, agent_id: UUID, tenant_id: UUID) -> Optional[Advisor]:
        advisor = self.advisors.get(agent_id)
        return advisor if advisor is not None and advisor.tenant_id.value == tenant_id else None

    def list_available(self, tenant_id: UUID, group_id: Optional[UUID] = None) -> List[Advisor]:
        return [a for a in self._routable(tenant_id, group_id) if a.is_active]

    def list(self, tenant_id, group_id=None, is_active=None, limit=100, offset=0) -> List[Advisor]:
        found = [a for a in self._routable(tenant_id, group_id) if is_active is None or a.is_active == is_active]
        return found[offset:offset + limit]

    def count_by_group(self, tenant_id: UUID, group_id: UUID) -> int:
        return len(self.list_available(tenant_id, group_id))

    def upsert_identity(self, advisor: Advisor) -> None:
        stored = self.advisors.get(advisor.agent_id.value)
        if stored is None:
            self.advisors[advisor.agent_id.value] = replace(advisor, group_id=None)
        elif stored.version < advisor.version:
            self.advisors[advisor.agent_id.value] = replace(advisor, group_id=stored.group_id)

    def set_group(self, agent_id: UUID, tenant_id: UUID, group_id: Optional[UUID]) -> bool:
        advisor = self.get(agent_id, tenant_id)
        if advisor is None:
            return False
        self.advisors[agent_id] = replace(advisor, group_id=GroupId(group_id) if group_id else None)
        return True

    def orphan_group(self, group_id: UUID) -> None:
        """What the foreign key's ON DELETE SET NULL does in Postgres."""
        for advisor in list(self.advisors.values()):
            if advisor.group_id is not None and advisor.group_id.value == group_id:
                self.advisors[advisor.agent_id.value] = replace(advisor, group_id=None)
