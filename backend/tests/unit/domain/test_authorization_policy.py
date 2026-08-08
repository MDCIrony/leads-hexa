from typing import Optional
from uuid import UUID, uuid4

import pytest

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole

_TENANT_A = uuid4()
_TENANT_B = uuid4()


def _agent(role: AgentRole, tenant_id: Optional[UUID] = None, agent_id: Optional[UUID] = None) -> Agent:
    return Agent.create(
        "Someone", "someone@test.com", "Sales", role=role, tenant_id=tenant_id, agent_id=agent_id
    )


class TestTenantAccess:
    def test_platform_admin_reaches_every_organization(self):
        admin = _agent(AgentRole.ADMIN, tenant_id=None)
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_A) is True
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_B) is True

    def test_manager_reaches_only_its_own_organization(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_A) is True
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_B) is False

    def test_agent_without_organization_reaches_nothing(self):
        orphan = _agent(AgentRole.AGENT, tenant_id=None)
        assert AuthorizationPolicy.can_access_tenant(orphan, _TENANT_A) is False

    def test_ensure_raises_forbidden_when_denied(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_access_tenant(manager, _TENANT_B)

    def test_ensure_is_silent_when_allowed(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        AuthorizationPolicy.ensure_can_access_tenant(manager, _TENANT_A)


class TestOrganizationManagement:
    def test_admin_and_manager_can_manage(self):
        assert AuthorizationPolicy.can_manage_organization(_agent(AgentRole.ADMIN)) is True
        assert AuthorizationPolicy.can_manage_organization(
            _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        ) is True

    def test_sales_agent_cannot_manage(self):
        assert AuthorizationPolicy.can_manage_organization(
            _agent(AgentRole.AGENT, tenant_id=_TENANT_A)
        ) is False


class TestAgentCreation:
    def test_only_platform_admin_creates_platform_admins(self):
        admin = _agent(AgentRole.ADMIN)
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_create_agent_with_role(admin, AgentRole.ADMIN) is True
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.ADMIN) is False

    def test_manager_creates_managers_and_agents(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.MANAGER) is True
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.AGENT) is True

    def test_sales_agent_creates_nobody(self):
        sales = _agent(AgentRole.AGENT, tenant_id=_TENANT_A)
        for role in AgentRole:
            assert AuthorizationPolicy.can_create_agent_with_role(sales, role) is False


class TestLeadVisibility:
    def test_manager_sees_every_lead_of_its_organization(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_view_lead(manager, _TENANT_A, uuid4()) is True

    def test_manager_does_not_see_another_organization_leads(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_view_lead(manager, _TENANT_B, uuid4()) is False

    def test_sales_agent_sees_only_leads_assigned_to_itself(self):
        own_id = uuid4()
        sales = _agent(AgentRole.AGENT, tenant_id=_TENANT_A, agent_id=own_id)
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, own_id) is True
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, uuid4()) is False

    def test_sales_agent_does_not_see_unassigned_leads(self):
        own_id = uuid4()
        sales = _agent(AgentRole.AGENT, tenant_id=_TENANT_A, agent_id=own_id)
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, None) is False
