from uuid import uuid4

from domain.entities.agent import Agent
from domain.entities.tenant import Tenant
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.cli.publish_identity_snapshot import publish_identity_snapshot


def _seed(test_db):
    tenant = Tenant.create(name="Acme", tenant_id=uuid4(), slug="acme")
    with PostgresUnitOfWork(test_db) as uow:
        uow.tenants.save(tenant)
        for index in range(3):
            uow.agents.save(Agent.create(
                f"Agent {index}", f"a{index}@acme.test", role=AgentRole.AGENT, tenant_id=tenant.id.value,
            ))
        # No organization: the platform admin is identity state too.
        uow.agents.save(Agent.create("Root", "root@platform.test", role=AgentRole.ADMIN))
        uow.agents.save(Agent.create(
            "Robot", "robot@acme.test", role=AgentRole.INTEGRATION, tenant_id=tenant.id.value, is_active=False,
        ))
    return tenant


def test_every_agent_and_tenant_is_recorded_across_pages(test_db):
    tenant = _seed(test_db)

    # page_size 2 against 5 agents: three pages, the last one short.
    counts = publish_identity_snapshot(lambda: PostgresUnitOfWork(test_db), page_size=2)

    assert counts == (5, 1)
    with open_outbox_store(test_db) as store:
        rows = store.fetch("internal", 100)
    agents = [row for row in rows if row.event_type == "AgentState"]
    assert len(agents) == 5
    assert len({row.partition_key for row in agents}) == 5
    assert any(row.tenant_id is None for row in agents)
    # Snapshot payloads never carry credentials or contact data.
    for row in agents:
        assert set(row.payload) == {"agent_id", "tenant_id", "name", "role", "is_active", "version"}
    (tenant_row,) = [row for row in rows if row.event_type == "TenantState"]
    assert tenant_row.partition_key == str(tenant.id.value)
    assert tenant_row.payload["version"] == 1


def test_an_empty_database_records_nothing(test_db):
    assert publish_identity_snapshot(lambda: PostgresUnitOfWork(test_db)) == (0, 0)
