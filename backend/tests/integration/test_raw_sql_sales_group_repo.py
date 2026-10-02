from types import SimpleNamespace

import psycopg
import pytest

from domain.groups.sales_group import SalesGroup
from domain.value_objects.enums import AssignmentStrategy
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import (
    RawSqlSalesGroupRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlSalesGroupRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> SimpleNamespace:
    # No row: since migration 017 nothing in leads_db references tenants.
    return SimpleNamespace(id=TenantId())


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
