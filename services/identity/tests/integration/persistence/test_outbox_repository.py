from chassis.web import request_id_var

from domain.agents.agent import Agent
from domain.events.identity_events import AgentState, TenantState
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole


def _rows(uow_factory):
    with uow_factory() as uow:
        return uow.connection.execute("SELECT * FROM outbox_events ORDER BY occurred_on").fetchall()


def test_records_the_event_with_its_own_id_key_and_payload(uow_factory):
    tenant = Tenant.create(name="Acme")
    event = TenantState.of(tenant)
    with uow_factory() as uow:
        uow.outbox.record(event)

    [row] = _rows(uow_factory)
    assert (row["id"], row["event_type"], row["partition_key"], row["channel"]) == (
        event.event_id, "TenantState", str(tenant.id), "internal",
    )
    assert str(row["tenant_id"]) == str(tenant.id)
    assert row["payload"] == event.as_payload()
    assert (row["published_at"], row["attempts"], row["correlation_id"]) == (None, 0, None)


def test_the_platform_admin_state_has_no_tenant(uow_factory):
    with uow_factory() as uow:
        uow.outbox.record(AgentState.of(Agent.create("Root", "root@platform.test", role=AgentRole.ADMIN)))

    assert _rows(uow_factory)[0]["tenant_id"] is None


def test_carries_the_id_of_the_request_that_caused_it(uow_factory):
    token = request_id_var.set("req-123")
    try:
        with uow_factory() as uow:
            uow.outbox.record(TenantState.of(Tenant.create(name="Acme")))
    finally:
        request_id_var.reset(token)

    assert _rows(uow_factory)[0]["correlation_id"] == "req-123"


def test_a_rollback_takes_the_event_along(uow_factory):
    try:
        with uow_factory() as uow:
            uow.outbox.record(TenantState.of(Tenant.create(name="Acme")))
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert _rows(uow_factory) == []
