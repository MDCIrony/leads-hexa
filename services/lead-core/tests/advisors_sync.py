"""Stand-ins for identity: the suite runs none, so tests seed what it would know.

`seed_advisor` registers an agent with the identity double and, unless told
otherwise, writes the projection row the consumer of internal.identity.agents
would have written. `IdentityDouble` answers hydration from that same map."""
from typing import Optional
from uuid import UUID, uuid4

from application.ports.output.advisors.identity_agents_port import IdentityAgentsPort
from domain.advisors.advisor import Advisor
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork

# What identity holds; conftest empties it before every test.
IDENTITY: dict[UUID, Advisor] = {}


class IdentityDouble(IdentityAgentsPort):
    """Takes HttpIdentityAgents' arguments so the Container builds it unchanged."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.calls = 0

    def fetch(self, agent_id):
        self.calls += 1
        return IDENTITY.get(UUID(str(agent_id)))


def seed_advisor(
    database,
    tenant_id,
    role: AgentRole = AgentRole.AGENT,
    name: str = "Agent",
    group_id=None,
    is_active: bool = True,
    projected: bool = True,
    agent_id: Optional[UUID] = None,
) -> Advisor:
    advisor = Advisor(AgentId(agent_id or uuid4()), TenantId(str(tenant_id)), name, role, is_active, 1)
    IDENTITY[advisor.agent_id.value] = advisor
    if projected:
        with PostgresUnitOfWork(database) as uow:
            uow.advisors.upsert_identity(advisor)
            if group_id:
                uow.advisors.set_group(advisor.agent_id.value, advisor.tenant_id.value, UUID(str(group_id)))
    return advisor


def project_identity(database) -> None:
    """What the advisors consumer leaves once every pending agent event has arrived."""
    with PostgresUnitOfWork(database) as uow:
        for advisor in IDENTITY.values():
            uow.advisors.upsert_identity(advisor)
