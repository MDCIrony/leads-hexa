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
