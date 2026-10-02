from uuid import uuid4

import pytest

from application.dtos.commands import CreateTenantCommand, UpdateTenantCommand
from application.dtos.queries import GetTenantsQuery
from application.use_cases.tenant_use_cases import (
    CreateTenantUseCase,
    GetTenantsUseCase,
    UpdateTenantUseCase,
)
from domain.entities.tenant import Tenant
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentRole
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_tenant_repo import InMemoryTenantRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        InMemoryAgentRepository(),
        tenants=InMemoryTenantRepository(),
    )


def _command(name: str = "Acme Corp", email: str = "ana@acme.test") -> CreateTenantCommand:
    return CreateTenantCommand(
        name=name,
        manager_name="Ana Ruiz",
        manager_email=email,
        manager_password="s3cret",
    )


class TestCreateTenant:
    def test_creates_the_organization_and_its_manager(self):
        uow = _uow()
        result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            _command()
        )
        assert result.tenant.name == "Acme Corp"
        assert result.tenant.slug == "acme-corp"
        assert result.manager.role == AgentRole.MANAGER

    def test_the_manager_belongs_to_the_new_organization(self):
        uow = _uow()
        result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            _command()
        )
        assert str(result.manager.tenant_id) == str(result.tenant.id)

    def test_the_manager_password_is_hashed(self):
        uow = _uow()
        result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            _command()
        )
        assert result.manager.hashed_password == "hashed:s3cret"

    def test_rejects_a_duplicate_organization_name(self):
        uow = _uow()
        use_case = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())
        use_case.execute(_command())
        with pytest.raises(DomainException):
            use_case.execute(_command(email="otra@acme.test"))

    def test_rejects_an_email_already_in_use(self):
        uow = _uow()
        use_case = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())
        use_case.execute(_command())
        with pytest.raises(DomainException):
            use_case.execute(_command(name="Other Corp"))

    def test_normalizes_the_manager_email_and_rejects_its_normalized_duplicate(self):
        uow = _uow()
        use_case = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())

        result = use_case.execute(_command(email="  Ana@Acme.Test "))

        assert result.manager.email == "ana@acme.test"
        with pytest.raises(DomainException) as exc_info:
            use_case.execute(_command(name="Other Corp", email="ANA@acme.test"))
        assert exc_info.value.error_code == "EMAIL_ALREADY_EXISTS"

    def test_a_rejected_creation_leaves_no_organization_behind(self):
        """Both writes share one transaction: a failed manager must not leave an
        unreachable organization."""
        uow = _uow()
        use_case = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())
        use_case.execute(_command())
        with pytest.raises(DomainException):
            use_case.execute(_command(name="Other Corp"))
        assert uow.tenants.count_all() == 1


class TestGetTenants:
    def test_returns_each_organization_with_its_agent_count(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        uow.tenants.set_agent_count(tenant.id.value, 4)

        page = GetTenantsUseCase(uow=uow).execute(GetTenantsQuery())

        assert page.total == 1
        assert page.items[0].tenant.name == "Acme Corp"
        assert page.items[0].agent_count == 4

    def test_paginates(self):
        uow = _uow()
        for name in ("Alpha", "Beta", "Gamma"):
            uow.tenants.save(Tenant.create(name=name))
        page = GetTenantsUseCase(uow=uow).execute(GetTenantsQuery(limit=2, offset=0))
        assert page.total == 3
        assert len(page.items) == 2


class TestUpdateTenant:
    def test_renames(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        updated = UpdateTenantUseCase(uow=uow).execute(
            UpdateTenantCommand(tenant_id=tenant.id.value, name="Acme Global")
        )
        assert updated.name == "Acme Global"

    def test_renaming_keeps_the_slug(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        updated = UpdateTenantUseCase(uow=uow).execute(
            UpdateTenantCommand(tenant_id=tenant.id.value, name="Acme Global")
        )
        assert updated.slug == "acme-corp"

    def test_deactivating_also_deactivates_its_users(self):
        """A valid credential of a suspended organization must stop working."""
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        from domain.entities.agent import Agent

        agent = uow.agents.save(
            Agent.create(
                "Ana", "ana@acme.test", role=AgentRole.MANAGER, tenant_id=tenant.id.value
            )
        )
        UpdateTenantUseCase(uow=uow).execute(
            UpdateTenantCommand(tenant_id=tenant.id.value, is_active=False)
        )
        assert uow.agents.get_by_id(agent.id.value).is_active is False

    def test_deactivating_reaches_past_one_page_of_users(self):
        """A paged loop would silently leave the users beyond the page active."""
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Big Corp"))
        from domain.entities.agent import Agent

        for index in range(150):
            uow.agents.save(
                Agent.create(
                    f"Agent {index:03d}",
                    f"agent{index}@big.test",
                    tenant_id=tenant.id.value,
                )
            )
        UpdateTenantUseCase(uow=uow).execute(
            UpdateTenantCommand(tenant_id=tenant.id.value, is_active=False)
        )
        assert uow.agents.count_by_tenant(tenant.id.value) == 0

    def test_unknown_organization_raises(self):
        uow = _uow()
        with pytest.raises(DomainException):
            UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=uuid4(), name="X"))


def _internal(uow: InMemoryUnitOfWork):
    return [(e.event_type, e.payload) for e in uow.outbox.list_unpublished("internal", 1000)]


class TestIdentityEvents:
    def test_creating_records_the_tenant_and_its_manager(self):
        uow = _uow()
        result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(_command())

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

    def test_suspending_records_the_tenant_and_every_agent_it_deactivated(self):
        from domain.entities.agent import Agent

        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        active = [
            uow.agents.save(Agent.create(f"A{i}", f"a{i}@acme.test", tenant_id=tenant.id.value))
            for i in range(2)
        ]
        uow.agents.save(Agent.create("Gone", "gone@acme.test", tenant_id=tenant.id.value, is_active=False))

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

    def test_renaming_records_the_new_state(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))

        UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=tenant.id.value, name="Acme Global"))

        assert _internal(uow) == [("TenantState", {
            "tenant_id": str(tenant.id.value), "name": "Acme Global", "slug": "acme-corp",
            "is_active": True, "version": 2,
        })]
