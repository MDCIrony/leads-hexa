from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from domain.agents.agent import Agent
from domain.tenants.tenant import Tenant
from infrastructure.adapters.output.persistence.agent_repository import PostgresAgentRepository
from infrastructure.adapters.output.persistence.tenant_repository import PostgresTenantRepository


@pytest.fixture
def conn(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        yield connection


@pytest.fixture
def repo(conn):
    return PostgresTenantRepository(conn)


def test_saves_and_reads_back_every_field(repo):
    saved = repo.save(Tenant.create(name="Acme Corp"))

    found = repo.get_by_id(saved.id.value)

    assert found == saved
    assert (found.name, found.slug, found.is_active) == ("Acme Corp", "acme-corp", True)


def test_finds_by_slug(repo):
    repo.save(Tenant.create(name="Acme Corp"))

    assert repo.get_by_slug("acme-corp") is not None
    assert repo.get_by_slug("nope") is None


def test_save_updates_an_existing_row(repo):
    tenant = repo.save(Tenant.create(name="Acme Corp"))
    tenant.rename("Acme Global")
    tenant.deactivate()
    repo.save(tenant)

    found = repo.get_by_id(tenant.id.value)
    assert (found.name, found.is_active) == ("Acme Global", False)
    assert repo.count_all() == 1


def test_duplicate_slug_is_rejected_by_the_database(repo):
    """The unique index is the real guarantee; application checks race."""
    repo.save(Tenant.create(name="Acme Corp"))

    with pytest.raises(psycopg.errors.UniqueViolation):
        repo.save(Tenant.create(name="Acme Corp", tenant_id=uuid4()))


def test_listing_orders_newest_first_and_pages_without_overlap(repo):
    # Explicit timestamps: a fast machine could save all three in the same microsecond.
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = repo.save(Tenant.create(name="Alpha", created_at=base))
    second = repo.save(Tenant.create(name="Beta", created_at=base + timedelta(minutes=1)))
    third = repo.save(Tenant.create(name="Gamma", created_at=base + timedelta(minutes=2)))

    assert [t.id for t in repo.list_all(limit=2)] == [third.id, second.id]
    assert [t.id for t in repo.list_all(limit=2, offset=2)] == [first.id]
    assert repo.count_all() == 3


def test_counts_only_active_agents_of_that_organization(repo, conn):
    tenant = repo.save(Tenant.create(name="Acme Corp"))
    other = repo.save(Tenant.create(name="Other Corp"))
    agents = PostgresAgentRepository(conn)
    for email, owner, active in (
        ("a@acme.test", tenant, True), ("b@acme.test", tenant, True),
        ("c@acme.test", tenant, False), ("d@other.test", other, True),
    ):
        agents.save(Agent.create("X", email, is_active=active, tenant_id=owner.id))

    assert repo.count_active_agents(tenant.id.value) == 2


def test_every_write_bumps_the_tenant_version(repo):
    saved = repo.save(Tenant.create(name="Acme Corp"))
    assert saved.version == 1

    saved.deactivate()
    saved = repo.save(saved)
    assert saved.version == 2
    assert repo.get_by_id(saved.id.value).version == 2
