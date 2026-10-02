from uuid import uuid4

import pytest

from application.dtos.tenants import CreateTenantCommand, GetTenantsQuery, UpdateTenantCommand
from application.use_cases.tenants.create_tenant import CreateTenantUseCase
from application.use_cases.tenants.manage_tenants import GetTenantsUseCase, UpdateTenantUseCase
from domain.agents.agent import Agent
from domain.exceptions import DomainException
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.services import FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _command(name: str = "Acme Corp", email: str = "ana@acme.test") -> CreateTenantCommand:
    return CreateTenantCommand(name=name, manager_name="Ana Ruiz", manager_email=email, manager_password="s3cret")


def _create_use_case(uow):
    return CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())


class TestCreateTenant:
    def test_creates_the_organization_and_its_manager_inside_it(self):
        result = _create_use_case(InMemoryUnitOfWork()).execute(_command())
        assert (result.tenant.name, result.tenant.slug) == ("Acme Corp", "acme-corp")
        assert result.manager.role == AgentRole.MANAGER
        assert str(result.manager.tenant_id) == str(result.tenant.id)

    def test_the_manager_password_is_hashed(self):
        result = _create_use_case(InMemoryUnitOfWork()).execute(_command())
        assert result.manager.hashed_password == "hashed:s3cret"

    def test_rejects_a_duplicate_organization_name(self):
        use_case = _create_use_case(InMemoryUnitOfWork())
        use_case.execute(_command())
        with pytest.raises(DomainException) as exc_info:
            use_case.execute(_command(email="otra@acme.test"))
        assert exc_info.value.error_code == "TENANT_ALREADY_EXISTS"

    def test_normalizes_the_manager_email_and_rejects_its_normalized_duplicate(self):
        use_case = _create_use_case(InMemoryUnitOfWork())
        result = use_case.execute(_command(email="  Ana@Acme.Test "))
        assert result.manager.email == "ana@acme.test"
        with pytest.raises(DomainException) as exc_info:
            use_case.execute(_command(name="Other Corp", email="ANA@acme.test"))
        assert exc_info.value.error_code == "EMAIL_ALREADY_EXISTS"

    def test_a_rejected_creation_leaves_no_organization_behind(self):
        """Both writes share one transaction: a failed manager must not leave an unreachable organization."""
        uow = InMemoryUnitOfWork()
        use_case = _create_use_case(uow)
        use_case.execute(_command())
        with pytest.raises(DomainException):
            use_case.execute(_command(name="Other Corp"))
        assert uow.tenants.count_all() == 1


class TestGetTenants:
    def test_returns_each_organization_with_its_agent_count(self):
        uow = InMemoryUnitOfWork()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        uow.tenants.set_agent_count(tenant.id.value, 4)

        page = GetTenantsUseCase(uow=uow).execute(GetTenantsQuery())

        assert page.total == 1
        assert (page.items[0].tenant.name, page.items[0].agent_count) == ("Acme Corp", 4)

    def test_paginates(self):
        uow = InMemoryUnitOfWork()
        for name in ("Alpha", "Beta", "Gamma"):
            uow.tenants.save(Tenant.create(name=name))
        page = GetTenantsUseCase(uow=uow).execute(GetTenantsQuery(limit=2, offset=0))
        assert (page.total, len(page.items)) == (3, 2)


class TestUpdateTenant:
    def test_renaming_keeps_the_slug(self):
        uow = InMemoryUnitOfWork()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        updated = UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=tenant.id.value, name="Acme Global"))
        assert (updated.name, updated.slug) == ("Acme Global", "acme-corp")

    def test_deactivating_also_deactivates_its_users(self):
        """A valid credential of a suspended organization must stop working."""
        uow = InMemoryUnitOfWork()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        agent = uow.agents.save(Agent.create("Ana", "ana@acme.test", role=AgentRole.MANAGER, tenant_id=tenant.id))

        UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=tenant.id.value, is_active=False))

        assert uow.tenants.get_by_id(tenant.id.value).is_active is False
        assert uow.agents.get_by_id(agent.id.value).is_active is False

    def test_deactivating_reaches_past_one_page_of_users(self):
        """A paged loop would silently leave the users beyond the page active."""
        uow = InMemoryUnitOfWork()
        tenant = uow.tenants.save(Tenant.create(name="Big Corp"))
        for index in range(150):
            uow.agents.save(Agent.create(f"Agent {index:03d}", f"agent{index}@big.test", tenant_id=tenant.id))

        UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=tenant.id.value, is_active=False))

        assert uow.agents.count_by_tenant(tenant.id.value) == 0

    def test_reactivating_does_not_reactivate_its_users(self):
        uow = InMemoryUnitOfWork()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp", is_active=False))
        agent = uow.agents.save(Agent.create("Ana", "ana@acme.test", tenant_id=tenant.id, is_active=False))

        UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=tenant.id.value, is_active=True))

        assert uow.tenants.get_by_id(tenant.id.value).is_active is True
        assert uow.agents.get_by_id(agent.id.value).is_active is False

    def test_unknown_organization_is_tenant_not_found(self):
        with pytest.raises(DomainException) as exc_info:
            UpdateTenantUseCase(uow=InMemoryUnitOfWork()).execute(UpdateTenantCommand(tenant_id=uuid4(), name="X"))
        assert exc_info.value.error_code == "TENANT_NOT_FOUND"
