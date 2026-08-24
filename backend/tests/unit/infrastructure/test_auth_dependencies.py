from uuid import uuid4

import pytest

from application.ports.output.token_service_port import TokenClaims
from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException, UnauthorizedException
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.api.dependencies import (
    build_request_context,
    resolve_current_agent,
    resolve_integration_context,
)
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.fake_token_service import FakeTokenService
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT_A = uuid4()
_HASHER = FakePasswordHasher()


class _StubContainer:
    """Only what require_manager_or_integration actually reads off it —
    the real Container's password_hasher is bcrypt, which this file avoids
    for the same reason FakePasswordHasher exists at all (~250ms/call)."""

    def __init__(self, password_hasher):
        self.password_hasher = password_hasher


def _integration_agent(secret: str = "s3cr3t", is_active: bool = True) -> Agent:
    return Agent.create(
        "Integración",
        "integration@a.invalid",
        role=AgentRole.INTEGRATION,
        hashed_password=_HASHER.hash(secret),
        tenant_id=_TENANT_A,
        is_active=is_active,
    )


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
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    resolved = resolve_current_agent(
        token=_token_for(agent), uow=_uow_with(agent), token_service=FakeTokenService()
    )
    assert str(resolved.id) == str(agent.id)


def test_malformed_token_is_unauthorized():
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(
            token="garbage", uow=_uow_with(agent), token_service=FakeTokenService()
        )


def test_deactivated_agent_is_unauthorized_even_with_a_valid_token():
    """Identity is revalidated against the database on every request, so
    deactivating an account cuts an outstanding token immediately."""
    agent = Agent.create(
        "M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A, is_active=False
    )
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(
            token=_token_for(agent), uow=_uow_with(agent), token_service=FakeTokenService()
        )


def test_context_carries_the_agent_own_tenant():
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    context = build_request_context(current_agent=agent)
    assert context.actor is agent
    assert str(context.tenant_id) == str(_TENANT_A)


def test_platform_admin_context_has_no_tenant():
    admin = Agent.create("A", "a@test.com", role=AgentRole.ADMIN, tenant_id=None)
    assert build_request_context(current_agent=admin).tenant_id is None


def test_sales_agent_is_refused_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    sales = Agent.create("S", "s@test.com", role=AgentRole.AGENT, tenant_id=_TENANT_A)
    with pytest.raises(ForbiddenException):
        require_organization_manager(context=build_request_context(current_agent=sales))


def test_manager_is_allowed_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    manager = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    context = build_request_context(current_agent=manager)
    assert require_organization_manager(context=context) is context


def test_resolve_integration_context_with_a_well_formed_key_resolves_the_agent():
    agent = _integration_agent()
    api_key = f"{agent.id}.s3cr3t"

    context = resolve_integration_context(api_key, uow=_uow_with(agent), password_hasher=_HASHER)

    assert str(context.actor.id) == str(agent.id)
    assert str(context.tenant_id) == str(_TENANT_A)


def test_resolve_integration_context_rejects_a_key_with_no_dot():
    agent = _integration_agent()
    with pytest.raises(UnauthorizedException):
        resolve_integration_context("no-dot-here", uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_context_rejects_a_non_uuid_agent_id():
    agent = _integration_agent()
    with pytest.raises(UnauthorizedException):
        resolve_integration_context("not-a-uuid.s3cr3t", uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_context_rejects_an_unknown_agent():
    agent = _integration_agent()
    api_key = f"{uuid4()}.s3cr3t"
    with pytest.raises(UnauthorizedException):
        resolve_integration_context(api_key, uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_context_rejects_an_inactive_agent():
    agent = _integration_agent(is_active=False)
    api_key = f"{agent.id}.s3cr3t"
    with pytest.raises(UnauthorizedException):
        resolve_integration_context(api_key, uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_context_rejects_a_non_integration_role():
    manager = Agent.create(
        "M", "m2@test.com", role=AgentRole.MANAGER, hashed_password=_HASHER.hash("s3cr3t"), tenant_id=_TENANT_A
    )
    api_key = f"{manager.id}.s3cr3t"
    with pytest.raises(UnauthorizedException):
        resolve_integration_context(api_key, uow=_uow_with(manager), password_hasher=_HASHER)


def test_resolve_integration_context_rejects_a_secret_that_does_not_verify():
    agent = _integration_agent()
    api_key = f"{agent.id}.wrong-secret"
    with pytest.raises(UnauthorizedException):
        resolve_integration_context(api_key, uow=_uow_with(agent), password_hasher=_HASHER)


def test_require_manager_or_integration_uses_the_api_key_path_without_checking_the_jwt():
    from infrastructure.adapters.input.api.dependencies import require_manager_or_integration

    agent = _integration_agent()
    api_key = f"{agent.id}.s3cr3t"

    context = require_manager_or_integration(
        api_key=api_key, current_agent=None, uow=_uow_with(agent), container=_StubContainer(_HASHER)
    )

    assert str(context.actor.id) == str(agent.id)


def test_require_manager_or_integration_falls_back_to_the_manager_jwt_path_without_a_key():
    from infrastructure.adapters.input.api.dependencies import require_manager_or_integration

    manager = Agent.create("M", "m3@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)

    context = require_manager_or_integration(
        api_key=None, current_agent=manager, uow=_uow_with(manager), container=_StubContainer(_HASHER)
    )

    assert context.actor is manager


def test_require_manager_or_integration_rejects_neither_credential():
    from infrastructure.adapters.input.api.dependencies import require_manager_or_integration

    with pytest.raises(UnauthorizedException):
        require_manager_or_integration(
            api_key=None,
            current_agent=None,
            uow=_uow_with(_integration_agent()),
            container=_StubContainer(_HASHER),
        )
