from uuid import uuid4

import pytest

from application.ports.output.token_service_port import TokenClaims
from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException, UnauthorizedException
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.api.dependencies import (
    build_request_context,
    resolve_current_agent,
)
from tests.unit.mocks.fake_token_service import FakeTokenService
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT_A = uuid4()


def _uow_with(agent: Agent) -> InMemoryUnitOfWork:
    repo = InMemoryAgentRepository()
    repo.save(agent)
    return InMemoryUnitOfWork(InMemoryLeadRepository(), InMemoryRuleRepository(), repo)


def _token_for(agent: Agent) -> str:
    return FakeTokenService().issue(
        TokenClaims(
            agent_id=str(agent.id),
            role=agent.role.value,
            tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
        )
    )


def test_valid_token_resolves_the_agent():
    agent = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    resolved = resolve_current_agent(
        token=_token_for(agent), uow=_uow_with(agent), token_service=FakeTokenService()
    )
    assert str(resolved.id) == str(agent.id)


def test_malformed_token_is_unauthorized():
    agent = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(
            token="garbage", uow=_uow_with(agent), token_service=FakeTokenService()
        )


def test_deactivated_agent_is_unauthorized_even_with_a_valid_token():
    """Identity is revalidated against the database on every request, so
    deactivating an account cuts an outstanding token immediately."""
    agent = Agent.create(
        "M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A, is_active=False
    )
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(
            token=_token_for(agent), uow=_uow_with(agent), token_service=FakeTokenService()
        )


def test_context_carries_the_agent_own_tenant():
    agent = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    context = build_request_context(current_agent=agent)
    assert context.actor is agent
    assert str(context.tenant_id) == str(_TENANT_A)


def test_platform_admin_context_has_no_tenant():
    admin = Agent.create("A", "a@test.com", "Platform", role=AgentRole.ADMIN, tenant_id=None)
    assert build_request_context(current_agent=admin).tenant_id is None


def test_sales_agent_is_refused_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    sales = Agent.create("S", "s@test.com", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_A)
    with pytest.raises(ForbiddenException):
        require_organization_manager(context=build_request_context(current_agent=sales))


def test_manager_is_allowed_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    manager = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    context = build_request_context(current_agent=manager)
    assert require_organization_manager(context=context) is context
