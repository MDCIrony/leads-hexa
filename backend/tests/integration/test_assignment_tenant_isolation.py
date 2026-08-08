import uuid

from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import (
    RawSqlAgentRepository,
)

_TENANT_A = uuid.uuid4()
_TENANT_B = uuid.uuid4()


def _agent(name: str, email: str, tenant_id: uuid.UUID, team: str = "Sales") -> Agent:
    return Agent.create(
        name=name,
        email=email,
        team=team,
        role=AgentRole.AGENT,
        tenant_id=tenant_id,
    )


def test_available_agents_never_cross_organizations(test_db):
    """A lead of one organization must never reach another's sales agents.

    Both organizations name their team "Sales", which is exactly the collision
    that made the leak invisible: the engine filtered by team name alone."""
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAgentRepository(conn)
        repo.save(_agent("Ana", "ana@a.test", _TENANT_A))
        repo.save(_agent("Bruno", "bruno@b.test", _TENANT_B))

        found = repo.get_available_agents(_TENANT_A)

        assert [a.email for a in found] == ["ana@a.test"]


def test_available_agents_still_filter_by_team(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAgentRepository(conn)
        repo.save(_agent("Ana", "ana@a.test", _TENANT_A, team="Sales"))
        repo.save(_agent("Carla", "carla@a.test", _TENANT_A, team="Support"))

        assert len(repo.get_available_agents(_TENANT_A, team="Sales")) == 1
        assert len(repo.get_available_agents(_TENANT_A)) == 2
