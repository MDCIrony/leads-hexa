import os
import uuid
import pytest
from fastapi import HTTPException

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")

from domain.entities.agent import Agent
from domain.exceptions import UnauthorizedException, ForbiddenException
from domain.value_objects.enums import AgentRole
from infrastructure.security.jwt_service import create_access_token
from infrastructure.adapters.input.api.dependencies import (
    get_current_agent,
    require_role,
    verify_tenant_access,
    require_role_and_tenant,
)
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _uow_with_agent(role=AgentRole.AGENT, is_active=True, tenant_id=None):
    repo = InMemoryAgentRepository()
    agent = Agent.create("Test", "t@test.com", "Sales", role=role, is_active=is_active, tenant_id=tenant_id)
    repo.save(agent)
    uow = InMemoryUnitOfWork(agents=repo)
    return uow, agent


def test_get_current_agent_returns_the_agent_for_a_valid_token():
    uow, agent = _uow_with_agent(role=AgentRole.MANAGER)
    token = create_access_token(agent_id=str(agent.id), role="MANAGER", tenant_id=None)
    resolved = get_current_agent(token=token, uow=uow)
    assert str(resolved.id) == str(agent.id)


def test_get_current_agent_rejects_an_invalid_token():
    uow, _ = _uow_with_agent()
    with pytest.raises(UnauthorizedException):
        get_current_agent(token="not-a-real-token", uow=uow)


def test_get_current_agent_rejects_an_inactive_agent():
    uow, agent = _uow_with_agent(is_active=False)
    token = create_access_token(agent_id=str(agent.id), role="AGENT", tenant_id=None)
    with pytest.raises(UnauthorizedException):
        get_current_agent(token=token, uow=uow)


def test_require_role_allows_a_permitted_role():
    _, agent = _uow_with_agent(role=AgentRole.ADMIN)
    dependency = require_role(AgentRole.ADMIN, AgentRole.MANAGER)
    assert dependency(current_agent=agent) is agent


def test_require_role_rejects_a_non_permitted_role():
    _, agent = _uow_with_agent(role=AgentRole.AGENT)
    dependency = require_role(AgentRole.ADMIN, AgentRole.MANAGER)
    with pytest.raises(ForbiddenException):
        dependency(current_agent=agent)


def test_verify_tenant_access_matching_tenant_allows():
    tenant_id = uuid.uuid4()
    _, agent = _uow_with_agent(role=AgentRole.AGENT, tenant_id=tenant_id)
    resolved = verify_tenant_access(tenant_id=tenant_id, current_agent=agent)
    assert resolved is agent


def test_verify_tenant_access_mismatched_tenant_raises_forbidden():
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    _, agent = _uow_with_agent(role=AgentRole.AGENT, tenant_id=tenant_id)
    with pytest.raises(ForbiddenException) as exc_info:
        verify_tenant_access(tenant_id=other_tenant_id, current_agent=agent)
    assert "do not have access to this tenant's data" in str(exc_info.value)


def test_verify_tenant_access_admin_allowed_for_any_tenant():
    admin_tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    _, admin_agent = _uow_with_agent(role=AgentRole.ADMIN, tenant_id=admin_tenant_id)
    resolved = verify_tenant_access(tenant_id=other_tenant_id, current_agent=admin_agent)
    assert resolved is admin_agent


def test_require_role_and_tenant_matching_role_and_tenant_allows():
    tenant_id = uuid.uuid4()
    _, agent = _uow_with_agent(role=AgentRole.MANAGER, tenant_id=tenant_id)
    dependency = require_role_and_tenant(AgentRole.ADMIN, AgentRole.MANAGER)
    resolved = dependency(tenant_id=tenant_id, current_agent=agent)
    assert resolved is agent


def test_require_role_and_tenant_mismatched_tenant_raises_forbidden():
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    _, agent = _uow_with_agent(role=AgentRole.MANAGER, tenant_id=tenant_id)
    dependency = require_role_and_tenant(AgentRole.ADMIN, AgentRole.MANAGER)
    with pytest.raises(ForbiddenException) as exc_info:
        dependency(tenant_id=other_tenant_id, current_agent=agent)
    assert "do not have access to this tenant's data" in str(exc_info.value)


def test_require_role_and_tenant_admin_allowed_for_any_tenant():
    other_tenant_id = uuid.uuid4()
    _, admin_agent = _uow_with_agent(role=AgentRole.ADMIN, tenant_id=None)
    dependency = require_role_and_tenant(AgentRole.ADMIN, AgentRole.MANAGER)
    resolved = dependency(tenant_id=other_tenant_id, current_agent=admin_agent)
    assert resolved is admin_agent


def test_require_role_and_tenant_wrong_role_rejected_before_checking_tenant():
    tenant_id = uuid.uuid4()
    _, agent = _uow_with_agent(role=AgentRole.AGENT, tenant_id=tenant_id)
    dependency = require_role_and_tenant(AgentRole.ADMIN, AgentRole.MANAGER)
    with pytest.raises(ForbiddenException) as exc_info:
        dependency(tenant_id=tenant_id, current_agent=agent)
    assert "Role AGENT is not permitted" in str(exc_info.value)


