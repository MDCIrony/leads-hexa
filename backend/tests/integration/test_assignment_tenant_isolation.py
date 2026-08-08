import uuid

from domain.entities.agent import Agent
from domain.entities.sales_group import SalesGroup
from domain.entities.tenant import Tenant
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import (
    RawSqlAgentRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import (
    RawSqlSalesGroupRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)

_TENANT_A = uuid.uuid4()
_TENANT_B = uuid.uuid4()


def test_available_agents_never_cross_organizations(test_db):
    """A lead of one organization must never reach another's sales agents.

    Before the fix the candidate pool was filtered by team name alone, so two
    organizations both calling their team "Sales" shared candidates."""
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAgentRepository(conn)
        repo.save(
            Agent.create("Ana", "ana@a.test", role=AgentRole.AGENT, tenant_id=_TENANT_A)
        )
        repo.save(
            Agent.create("Bruno", "bruno@b.test", role=AgentRole.AGENT, tenant_id=_TENANT_B)
        )

        found = repo.get_available_agents(_TENANT_A)

        assert [a.email for a in found] == ["ana@a.test"]


def test_available_agents_still_filter_by_group(test_db):
    """The group filter narrows the pool without ever widening it past the
    organization: group_id is a real foreign key now, not a free string."""
    with test_db.get_connection(autocommit=True) as conn:
        tenant = RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid.uuid4()}"))
        group_repo = RawSqlSalesGroupRepository(conn)
        sales = group_repo.save(SalesGroup.create(tenant_id=tenant.id.value, name="Sales"))
        support = group_repo.save(SalesGroup.create(tenant_id=tenant.id.value, name="Support"))

        repo = RawSqlAgentRepository(conn)
        repo.save(
            Agent.create(
                "Ana", "ana-g@a.test", sales.id.value,
                role=AgentRole.AGENT, tenant_id=tenant.id.value,
            )
        )
        repo.save(
            Agent.create(
                "Carla", "carla-g@a.test", support.id.value,
                role=AgentRole.AGENT, tenant_id=tenant.id.value,
            )
        )

        assert len(repo.get_available_agents(tenant.id.value, group_id=sales.id.value)) == 1
        assert len(repo.get_available_agents(tenant.id.value)) == 2


def test_a_group_of_another_organization_yields_no_candidates(test_db):
    """The organization filter wins over the group filter. Without it, knowing
    a group id would be enough to reach that group's agents from outside."""
    with test_db.get_connection(autocommit=True) as conn:
        tenant_a = RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org A {uuid.uuid4()}"))
        tenant_b = RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org B {uuid.uuid4()}"))
        group_repo = RawSqlSalesGroupRepository(conn)
        # Both organizations name their group "Sales" — the collision that made
        # the original leak invisible.
        group_a = group_repo.save(SalesGroup.create(tenant_id=tenant_a.id.value, name="Sales"))
        group_repo.save(SalesGroup.create(tenant_id=tenant_b.id.value, name="Sales"))

        repo = RawSqlAgentRepository(conn)
        repo.save(
            Agent.create(
                "Ana", "ana-x@a.test", group_a.id.value,
                role=AgentRole.AGENT, tenant_id=tenant_a.id.value,
            )
        )

        assert repo.get_available_agents(tenant_b.id.value, group_id=group_a.id.value) == []
