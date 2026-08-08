from typing import Optional
from uuid import UUID, uuid4

import pytest

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole

_TENANT_A = uuid4()
_TENANT_B = uuid4()


def _agent(
    role: AgentRole,
    tenant_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
) -> Agent:
    return Agent.create(
        "Someone", "someone@test.com", "Sales", role=role, tenant_id=tenant_id, agent_id=agent_id
    )


def _admin() -> Agent:
    return _agent(AgentRole.ADMIN, tenant_id=None)


def _manager(tenant_id: UUID = _TENANT_A) -> Agent:
    return _agent(AgentRole.MANAGER, tenant_id=tenant_id)


def _sales(tenant_id: UUID = _TENANT_A, agent_id: Optional[UUID] = None) -> Agent:
    return _agent(AgentRole.AGENT, tenant_id=tenant_id, agent_id=agent_id)


class TestPlaneSeparation:
    def test_platform_admin_manages_the_platform(self):
        assert AuthorizationPolicy.can_manage_platform(_admin()) is True

    def test_nobody_else_manages_the_platform(self):
        assert AuthorizationPolicy.can_manage_platform(_manager()) is False
        assert AuthorizationPolicy.can_manage_platform(_sales()) is False

    def test_platform_admin_does_not_manage_an_organization(self):
        """The whole point of this phase: the administrator is not a superset
        of the manager, it is a different plane."""
        assert AuthorizationPolicy.can_manage_organization(_admin()) is False

    def test_manager_manages_its_organization(self):
        assert AuthorizationPolicy.can_manage_organization(_manager()) is True

    def test_sales_agent_manages_nothing(self):
        assert AuthorizationPolicy.can_manage_organization(_sales()) is False


class TestTenantAccess:
    def test_platform_admin_reaches_no_organization_data(self):
        admin = _admin()
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_A) is False
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_B) is False

    def test_manager_reaches_only_its_own(self):
        manager = _manager()
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_A) is True
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_B) is False

    def test_agent_without_organization_reaches_nothing(self):
        assert AuthorizationPolicy.can_access_tenant(_agent(AgentRole.AGENT), _TENANT_A) is False

    def test_ensure_raises_for_the_platform_admin_too(self):
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_access_tenant(_admin(), _TENANT_A)

    def test_ensure_is_silent_when_allowed(self):
        AuthorizationPolicy.ensure_can_access_tenant(_manager(), _TENANT_A)


class TestAgentCreation:
    def test_manager_creates_managers_and_agents(self):
        manager = _manager()
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.MANAGER) is True
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.AGENT) is True

    def test_nobody_creates_a_platform_admin_through_this_path(self):
        """The single platform administrator comes from bootstrap; no API path
        mints another one."""
        for actor in (_admin(), _manager(), _sales()):
            assert AuthorizationPolicy.can_create_agent_with_role(actor, AgentRole.ADMIN) is False

    def test_platform_admin_does_not_create_organization_users_directly(self):
        admin = _admin()
        assert AuthorizationPolicy.can_create_agent_with_role(admin, AgentRole.MANAGER) is False
        assert AuthorizationPolicy.can_create_agent_with_role(admin, AgentRole.AGENT) is False

    def test_sales_agent_creates_nobody(self):
        for role in AgentRole:
            assert AuthorizationPolicy.can_create_agent_with_role(_sales(), role) is False

    def test_ensure_raises_when_denied(self):
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_create_agent_with_role(_sales(), AgentRole.AGENT)


class TestAgentListing:
    def test_only_the_manager_lists_agents(self):
        assert AuthorizationPolicy.can_list_agents(_manager()) is True
        assert AuthorizationPolicy.can_list_agents(_sales()) is False
        assert AuthorizationPolicy.can_list_agents(_admin()) is False

    def test_ensure_raises_for_a_sales_agent(self):
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_list_agents(_sales())


class TestLeadVisibility:
    def test_manager_sees_every_lead_of_its_organization(self):
        assert AuthorizationPolicy.can_view_lead(_manager(), _TENANT_A, uuid4()) is True

    def test_manager_does_not_see_another_organization_leads(self):
        assert AuthorizationPolicy.can_view_lead(_manager(), _TENANT_B, uuid4()) is False

    def test_platform_admin_sees_no_leads_at_all(self):
        assert AuthorizationPolicy.can_view_lead(_admin(), _TENANT_A, uuid4()) is False

    def test_sales_agent_sees_only_its_own(self):
        own = uuid4()
        sales = _sales(agent_id=own)
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, own) is True
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, uuid4()) is False

    def test_sales_agent_does_not_see_unassigned_leads(self):
        own = uuid4()
        assert AuthorizationPolicy.can_view_lead(_sales(agent_id=own), _TENANT_A, None) is False
