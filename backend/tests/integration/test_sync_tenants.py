from uuid import uuid4

from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.cli.sync_tenants import sync_tenants


def test_creates_one_organization_per_orphan_tenant_id(test_db):
    orphan_a, orphan_b = uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        for email, tid in (("a@x.test", orphan_a), ("b@x.test", orphan_a), ("c@y.test", orphan_b)):
            conn.execute(
                "INSERT INTO agents (id, name, email, team, active_leads_count,"
                " is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (str(uuid4()), "X", email, "Sales", 0, True, "AGENT", str(tid)),
            )

    created = sync_tenants(PostgresUnitOfWork(test_db))

    assert len(created) == 2
    with PostgresUnitOfWork(test_db) as uow:
        assert uow.tenants.get_by_id(orphan_a) is not None
        assert uow.tenants.get_by_id(orphan_b) is not None


def test_is_idempotent(test_db):
    orphan = uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email, team, active_leads_count,"
            " is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(uuid4()), "X", "a@x.test", "Sales", 0, True, "AGENT", str(orphan)),
        )

    assert len(sync_tenants(PostgresUnitOfWork(test_db))) == 1
    assert sync_tenants(PostgresUnitOfWork(test_db)) == []


def test_ignores_the_platform_admin(test_db):
    """The platform administrator has no organization by design; it must not
    produce a phantom one."""
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email, team, active_leads_count,"
            " is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL)",
            (str(uuid4()), "Admin", "admin@p.test", "HQ", 0, True, AgentRole.ADMIN.value),
        )
    assert sync_tenants(PostgresUnitOfWork(test_db)) == []
