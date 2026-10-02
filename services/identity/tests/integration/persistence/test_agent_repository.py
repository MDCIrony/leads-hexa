from uuid import uuid4

import psycopg
import pytest

from domain.agents.agent import Agent
from domain.value_objects.agent_role import AgentRole
from infrastructure.adapters.output.persistence.agent_repository import PostgresAgentRepository

_TENANT_A = uuid4()
_TENANT_B = uuid4()


@pytest.fixture
def repo(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        yield PostgresAgentRepository(conn)


@pytest.fixture
def seeded(repo):
    repo.save(Agent.create("A One", "a1@a.test", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    repo.save(Agent.create("A Two", "a2@a.test", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    other = repo.save(Agent.create("B One", "b1@b.test", role=AgentRole.AGENT, tenant_id=_TENANT_B))
    return repo, other


def test_saves_and_reads_back_every_field(repo):
    agent = repo.save(Agent.create(
        "Ana", "ana@acme.test", role=AgentRole.MANAGER, hashed_password="hash", tenant_id=_TENANT_A,
    ))

    found = repo.get_by_id(agent.id.value)

    assert found == agent
    assert repo.get_by_id(uuid4()) is None


def test_listing_returns_only_the_requested_organization(seeded):
    """The regression test for the cross-tenant leak."""
    repo, _ = seeded
    assert {a.email for a in repo.list_by_tenant(_TENANT_A)} == {"a1@a.test", "a2@a.test"}


def test_counting_is_scoped_too(seeded):
    repo, _ = seeded
    assert repo.count_by_tenant(_TENANT_A) == 2
    assert repo.count_by_tenant(_TENANT_B) == 1
    assert repo.count() == 3


def test_reading_an_agent_of_another_organization_returns_nothing(seeded):
    repo, other = seeded
    assert repo.get_by_id_and_tenant(other.id.value, _TENANT_B) is not None
    assert repo.get_by_id_and_tenant(other.id.value, _TENANT_A) is None


def test_the_active_filter_selects_either_state_or_both(seeded):
    repo, _ = seeded
    inactive = repo.save(Agent.create("A Zero", "a0@a.test", is_active=False, tenant_id=_TENANT_A))

    assert [a.id for a in repo.list_by_tenant(_TENANT_A, is_active=False)] == [inactive.id]
    assert repo.count_by_tenant(_TENANT_A, is_active=None) == 3
    assert len(repo.list_by_tenant(_TENANT_A, is_active=None)) == 3


def test_listing_is_ordered_by_name_and_paginated(seeded):
    repo, _ = seeded
    assert [a.name for a in repo.list_by_tenant(_TENANT_A, limit=1)] == ["A One"]
    assert [a.name for a in repo.list_by_tenant(_TENANT_A, limit=1, offset=1)] == ["A Two"]


def test_the_tenant_listing_excludes_the_integration_credential(seeded):
    """ADR-0028: a machine credential is not one of the manager's advisors."""
    repo, _ = seeded
    repo.save(Agent.create("Integración", "integration@a.invalid", role=AgentRole.INTEGRATION, tenant_id=_TENANT_A))

    assert {a.email for a in repo.list_by_tenant(_TENANT_A)} == {"a1@a.test", "a2@a.test"}
    assert repo.count_by_tenant(_TENANT_A) == 2


def test_email_lookup_is_case_insensitive_and_unique_globally(repo):
    first = repo.save(Agent.create("A", "  Agent@Acme.Test ", tenant_id=uuid4()))

    assert repo.get_by_email("agent@acme.test").id == first.id
    with pytest.raises(psycopg.errors.UniqueViolation):
        repo.save(Agent.create("B", "agent@ACME.test", tenant_id=uuid4()))


def test_every_write_bumps_the_agent_version(repo):
    """A projection applies a state only if it is newer, so version must grow on each write."""
    saved = repo.save(Agent.create("A One", "a1@a.test", tenant_id=_TENANT_A))
    assert saved.version == 1

    saved.name = "A Uno"
    saved = repo.save(saved)
    assert saved.version == 2
    assert repo.get_by_id(saved.id.value).version == 2


def test_deactivating_a_tenant_returns_its_agents_with_their_new_version(seeded):
    repo, other = seeded

    affected = repo.deactivate_all_by_tenant(_TENANT_A)

    assert {(a.email, a.is_active, a.version) for a in affected} == {("a1@a.test", False, 2), ("a2@a.test", False, 2)}
    assert repo.get_by_id(other.id.value).is_active is True
    assert repo.deactivate_all_by_tenant(_TENANT_A) == []


def test_the_snapshot_reads_cover_every_agent_and_organization(seeded):
    repo, _ = seeded
    admin = repo.save(Agent.create("Root", "root@platform.test", role=AgentRole.ADMIN))

    assert set(repo.distinct_tenant_ids()) == {_TENANT_A, _TENANT_B}
    everyone = repo.list_all(limit=2) + repo.list_all(limit=2, offset=2)
    assert len({a.id for a in everyone}) == 4 and admin.id in {a.id for a in everyone}
