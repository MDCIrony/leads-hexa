from uuid import uuid4

import psycopg
import pytest

from domain.entities.agent import Agent
from domain.entities.sales_group import SalesGroup
from domain.entities.tenant import Tenant
from domain.value_objects.enums import AgentRole, AssignmentStrategy
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import (
    RawSqlAgentRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import (
    RawSqlSalesGroupRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlSalesGroupRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> Tenant:
    # A real row is required: sales_groups.tenant_id has a foreign key to
    # tenants (migration 003), unlike the looser agents.tenant_id.
    return RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))


def test_saves_and_reads_back_every_field(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        saved = repo.save(
            SalesGroup.create(
                tenant_id=tenant.id.value,
                name="Ventas Norte",
                description="Equipo de ventas de la región norte",
                default_strategy=AssignmentStrategy.ROUND_ROBIN,
                capacity_per_agent=5,
            )
        )

        found = repo.get_by_id(saved.id.value)
        assert found is not None
        assert found.name == "Ventas Norte"
        assert found.description == "Equipo de ventas de la región norte"
        assert found.default_strategy == AssignmentStrategy.ROUND_ROBIN
        assert found.capacity_per_agent == 5
        assert found.is_active is True
        assert found.tenant_id.value == tenant.id.value
    finally:
        ctx.__exit__(None, None, None)


def test_listing_does_not_leak_into_another_organization(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant_a = _tenant(conn)
        tenant_b = _tenant(conn)
        repo.save(SalesGroup.create(tenant_id=tenant_a.id.value, name="Norte"))
        repo.save(SalesGroup.create(tenant_id=tenant_a.id.value, name="Sur"))
        repo.save(SalesGroup.create(tenant_id=tenant_b.id.value, name="Norte"))

        found = repo.list_by_tenant(tenant_a.id.value)

        assert {g.name for g in found} == {"Norte", "Sur"}
        assert repo.count_by_tenant(tenant_a.id.value) == 2
        assert repo.count_by_tenant(tenant_b.id.value) == 1
    finally:
        ctx.__exit__(None, None, None)


def test_duplicate_name_within_the_same_organization_is_rejected(test_db):
    """The unique index is the real guarantee; application checks race."""
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        repo.save(SalesGroup.create(tenant_id=tenant.id.value, name="Ventas"))
        with pytest.raises(psycopg.errors.UniqueViolation):
            repo.save(SalesGroup.create(tenant_id=tenant.id.value, name="Ventas"))
    finally:
        ctx.__exit__(None, None, None)


def test_the_same_name_is_allowed_in_two_different_organizations(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant_a = _tenant(conn)
        tenant_b = _tenant(conn)
        repo.save(SalesGroup.create(tenant_id=tenant_a.id.value, name="Ventas"))

        # Must not raise: the uniqueness constraint is scoped per tenant.
        repo.save(SalesGroup.create(tenant_id=tenant_b.id.value, name="Ventas"))

        assert repo.count_by_tenant(tenant_a.id.value) == 1
        assert repo.count_by_tenant(tenant_b.id.value) == 1
    finally:
        ctx.__exit__(None, None, None)


def test_deleting_a_group_orphans_its_agents_instead_of_deleting_them(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        group = repo.save(SalesGroup.create(tenant_id=tenant.id.value, name="Ventas"))
        agent_repo = RawSqlAgentRepository(conn)
        agent = agent_repo.save(
            Agent.create(
                name="Ana",
                email="ana@a.test",
                group_id=group.id.value,
                role=AgentRole.AGENT,
                tenant_id=tenant.id.value,
            )
        )

        repo.delete(group.id.value)

        assert repo.get_by_id(group.id.value) is None
        survivor = agent_repo.get_by_id(agent.id.value)
        assert survivor is not None
        assert survivor.group_id is None
    finally:
        ctx.__exit__(None, None, None)
