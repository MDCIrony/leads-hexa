"""Every tenant write records its TenantState, and every agent it touches its AgentState."""
from application.dtos.tenants import CreateTenantCommand, UpdateTenantCommand
from application.use_cases.tenants.create_tenant import CreateTenantUseCase
from application.use_cases.tenants.manage_tenants import UpdateTenantUseCase
from domain.agents.agent import Agent
from domain.tenants.tenant import Tenant
from tests.unit.application.doubles.services import FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _internal(uow: InMemoryUnitOfWork) -> list[tuple[str, dict]]:
    assert {e.channel for e in uow.events()} <= {"internal"}
    return [(e.event_type, e.payload) for e in uow.events()]


def test_creating_records_the_tenant_and_its_manager_and_nothing_else():
    uow = InMemoryUnitOfWork()
    result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(CreateTenantCommand(
        name="Acme Corp", manager_name="Ana Ruiz", manager_email="ana@acme.test", manager_password="s3cret",
    ))

    events = _internal(uow)
    assert [event_type for event_type, _ in events] == ["TenantState", "AgentState"]
    tenant_state, manager_state = events[0][1], events[1][1]
    assert tenant_state == {
        "tenant_id": str(result.tenant.id.value), "name": "Acme Corp", "slug": "acme-corp",
        "is_active": True, "version": 1,
    }
    assert manager_state["agent_id"] == str(result.manager.id)
    assert manager_state["tenant_id"] == str(result.tenant.id.value)
    assert manager_state["version"] == 1
    assert "email" not in manager_state and "hashed_password" not in manager_state


def test_suspending_records_the_tenant_and_every_agent_it_deactivated():
    uow = InMemoryUnitOfWork()
    tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
    active = [uow.agents.save(Agent.create(f"A{i}", f"a{i}@acme.test", tenant_id=tenant.id)) for i in range(2)]
    uow.agents.save(Agent.create("Gone", "gone@acme.test", tenant_id=tenant.id, is_active=False))

    UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=tenant.id.value, is_active=False))

    events = _internal(uow)
    tenant_states = [payload for event_type, payload in events if event_type == "TenantState"]
    agent_states = [payload for event_type, payload in events if event_type == "AgentState"]
    assert tenant_states == [{
        "tenant_id": str(tenant.id.value), "name": "Acme Corp", "slug": "acme-corp",
        "is_active": False, "version": 2,
    }]
    # The already inactive agent was not written, so it emits nothing.
    assert sorted(p["agent_id"] for p in agent_states) == sorted(str(a.id) for a in active)
    assert all(p["is_active"] is False and p["version"] == 2 for p in agent_states)


def test_renaming_records_the_new_state():
    uow = InMemoryUnitOfWork()
    tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))

    UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=tenant.id.value, name="Acme Global"))

    assert _internal(uow) == [("TenantState", {
        "tenant_id": str(tenant.id.value), "name": "Acme Global", "slug": "acme-corp",
        "is_active": True, "version": 2,
    })]
