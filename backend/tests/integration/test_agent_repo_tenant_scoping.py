from uuid import uuid4

from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import (
    RawSqlAgentRepository,
)

_TENANT_A = uuid4()
_TENANT_B = uuid4()


def _seed(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    repo = RawSqlAgentRepository(conn)
    repo.save(Agent.create("A One", "a1@a.test", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    repo.save(Agent.create("A Two", "a2@a.test", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    b = repo.save(
        Agent.create("B One", "b1@b.test", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_B)
    )
    return repo, ctx, b


def test_listing_returns_only_the_requested_organization(test_db):
    """The regression test for the cross-tenant leak: before this change any
    authenticated user could enumerate every organization's agents."""
    repo, ctx, _ = _seed(test_db)
    try:
        found = repo.list_by_tenant(_TENANT_A)
        assert len(found) == 2
        assert {a.email for a in found} == {"a1@a.test", "a2@a.test"}
    finally:
        ctx.__exit__(None, None, None)


def test_counting_is_scoped_too(test_db):
    repo, ctx, _ = _seed(test_db)
    try:
        assert repo.count_by_tenant(_TENANT_A) == 2
        assert repo.count_by_tenant(_TENANT_B) == 1
    finally:
        ctx.__exit__(None, None, None)


def test_reading_an_agent_of_another_organization_returns_nothing(test_db):
    repo, ctx, b_agent = _seed(test_db)
    try:
        assert repo.get_by_id_and_tenant(b_agent.id.value, _TENANT_B) is not None
        assert repo.get_by_id_and_tenant(b_agent.id.value, _TENANT_A) is None
    finally:
        ctx.__exit__(None, None, None)


def test_team_filter_composes_with_the_organization_filter(test_db):
    repo, ctx, _ = _seed(test_db)
    try:
        repo.save(
            Agent.create("A Three", "a3@a.test", "Support", role=AgentRole.AGENT, tenant_id=_TENANT_A)
        )
        assert len(repo.list_by_tenant(_TENANT_A, team="Sales")) == 2
        assert len(repo.list_by_tenant(_TENANT_A, team="Support")) == 1
        assert repo.count_by_tenant(_TENANT_A, team="Support") == 1
    finally:
        ctx.__exit__(None, None, None)


def test_listing_is_deterministically_ordered(test_db):
    repo, ctx, _ = _seed(test_db)
    try:
        assert [a.email for a in repo.list_by_tenant(_TENANT_A)] == [
            a.email for a in repo.list_by_tenant(_TENANT_A)
        ]
    finally:
        ctx.__exit__(None, None, None)
