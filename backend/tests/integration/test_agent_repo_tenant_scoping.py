from uuid import uuid4

import psycopg
import pytest

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

_TENANT_A = uuid4()
_TENANT_B = uuid4()


def _seed(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    repo = RawSqlAgentRepository(conn)
    # No group_id: these three tests are about tenant scoping, not group
    # membership, and agents.group_id is optional.
    repo.save(Agent.create("A One", "a1@a.test", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    repo.save(Agent.create("A Two", "a2@a.test", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    b = repo.save(
        Agent.create("B One", "b1@b.test", role=AgentRole.AGENT, tenant_id=_TENANT_B)
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


def test_group_filter_composes_with_the_organization_filter(test_db):
    """team used to be a free-form string; group_id is now a real foreign
    key, so exercising the filter needs an actual sales_groups row."""
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    try:
        tenant = RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))
        group_repo = RawSqlSalesGroupRepository(conn)
        sales = group_repo.save(SalesGroup.create(tenant_id=tenant.id.value, name="Sales"))
        support = group_repo.save(SalesGroup.create(tenant_id=tenant.id.value, name="Support"))

        repo = RawSqlAgentRepository(conn)
        repo.save(Agent.create("A One", "a1@a.test", sales.id.value, role=AgentRole.AGENT, tenant_id=tenant.id.value))
        repo.save(Agent.create("A Two", "a2@a.test", sales.id.value, role=AgentRole.AGENT, tenant_id=tenant.id.value))
        repo.save(Agent.create("A Three", "a3@a.test", support.id.value, role=AgentRole.AGENT, tenant_id=tenant.id.value))

        assert len(repo.list_by_tenant(tenant.id.value, group_id=sales.id.value)) == 2
        assert len(repo.list_by_tenant(tenant.id.value, group_id=support.id.value)) == 1
        assert repo.count_by_tenant(tenant.id.value, group_id=support.id.value) == 1
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


def test_list_by_tenant_excludes_the_integration_credential(test_db):
    """A machine credential lives in `agents` to reuse the password hash and
    the deactivation path (ADR-0028), not because it belongs in the manager's
    advisor template."""
    repo, ctx, _ = _seed(test_db)
    try:
        repo.save(
            Agent.create(
                "Integración", "integration@a.invalid", role=AgentRole.INTEGRATION, tenant_id=_TENANT_A
            )
        )
        found = repo.list_by_tenant(_TENANT_A)
        assert len(found) == 2
        assert {a.email for a in found} == {"a1@a.test", "a2@a.test"}
    finally:
        ctx.__exit__(None, None, None)


def test_get_available_agents_excludes_the_integration_credential(test_db):
    """Same exclusion for the assignment engine's candidate pool: a machine
    credential must never be nameable in a rule, or it would end up assigned
    leads nobody works (ADR-0028)."""
    repo, ctx, _ = _seed(test_db)
    try:
        repo.save(
            Agent.create(
                "Integración", "integration@a.invalid", role=AgentRole.INTEGRATION, tenant_id=_TENANT_A
            )
        )
        found = repo.get_available_agents(_TENANT_A)
        assert len(found) == 2
        assert {a.email for a in found} == {"a1@a.test", "a2@a.test"}
    finally:
        ctx.__exit__(None, None, None)


def test_email_lookup_is_case_insensitive_and_unique_globally(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    try:
        repo = RawSqlAgentRepository(conn)
        first = repo.save(Agent.create("A", "  Agent@Acme.Test ", tenant_id=uuid4()))

        assert repo.get_by_email("AGENT@acme.test").id == first.id
        with pytest.raises(psycopg.errors.UniqueViolation):
            repo.save(Agent.create("B", "agent@ACME.test", tenant_id=uuid4()))
    finally:
        ctx.__exit__(None, None, None)
