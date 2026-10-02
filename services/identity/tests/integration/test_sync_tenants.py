from uuid import uuid4

from domain.value_objects.agent_role import AgentRole
from infrastructure.cli.sync_tenants import sync_tenants


def _insert_agent(test_db, email, tenant_id, role="AGENT"):
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email, is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s)",
            (str(uuid4()), "X", email, True, role, str(tenant_id) if tenant_id else None),
        )


def test_creates_one_organization_per_orphan_tenant_id(test_db, uow_factory):
    orphan_a, orphan_b = uuid4(), uuid4()
    for email, tenant_id in (("a@x.test", orphan_a), ("b@x.test", orphan_a), ("c@y.test", orphan_b)):
        _insert_agent(test_db, email, tenant_id)

    created = sync_tenants(uow_factory())

    assert len(created) == 2
    with uow_factory() as uow:
        assert uow.tenants.get_by_id(orphan_a) is not None
        assert uow.tenants.get_by_id(orphan_b) is not None


def test_is_idempotent(test_db, uow_factory):
    _insert_agent(test_db, "a@x.test", uuid4())

    assert len(sync_tenants(uow_factory())) == 1
    assert sync_tenants(uow_factory()) == []


def test_ignores_the_platform_admin(test_db, uow_factory):
    """The platform administrator has no organization by design; it must not
    produce a phantom one."""
    _insert_agent(test_db, "admin@p.test", None, role=AgentRole.ADMIN.value)

    assert sync_tenants(uow_factory()) == []


def test_each_created_organization_is_announced_on_the_internal_channel(test_db, uow_factory):
    orphan = uuid4()
    _insert_agent(test_db, "a@x.test", orphan)

    sync_tenants(uow_factory())

    with uow_factory() as uow:
        rows = uow.connection.execute("SELECT event_type, partition_key, channel FROM outbox_events").fetchall()
    assert [(r["event_type"], r["partition_key"], r["channel"]) for r in rows] == [
        ("TenantState", str(orphan), "internal"),
    ]
