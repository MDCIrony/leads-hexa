from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest

from application.use_cases.auth.introspect import IntrospectUseCase
from domain.agents.agent import Agent
from domain.exceptions import UnauthorizedException
from domain.sessions.auth_session import AuthSession
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.services import FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork

_SECRET = "api-secret"


@pytest.fixture
def world():
    uow = InMemoryUnitOfWork()
    hasher = FakePasswordHasher()
    tenant = uow.tenants.save(Tenant.create(name="Acme"))
    human = uow.agents.save(Agent.create("Ana", "ana@acme.test", role=AgentRole.MANAGER, tenant_id=tenant.id))
    machine = uow.agents.save(Agent.create(
        "Integración", "integration@acme.invalid", role=AgentRole.INTEGRATION,
        hashed_password=hasher.hash(_SECRET), tenant_id=tenant.id,
    ))
    now = datetime.now(timezone.utc)
    uow.sessions.save(AuthSession(sha256(b"session").hexdigest(), human.id.value, now, now + timedelta(hours=1)))
    return uow, IntrospectUseCase(uow, hasher), tenant, human, machine


def test_a_live_session_resolves_to_its_human_agent(world):
    _, use_case, _, human, _ = world
    result = use_case.execute(None, "session")
    assert result.agent is human and result.principal_type == "human"


def test_a_valid_api_key_resolves_to_its_integration_agent(world):
    _, use_case, _, _, machine = world
    result = use_case.execute(f"{machine.id}.{_SECRET}", None)
    assert result.agent is machine and result.principal_type == "integration"


def test_the_api_key_wins_over_the_cookie(world):
    _, use_case, _, _, machine = world
    assert use_case.execute(f"{machine.id}.{_SECRET}", "session").principal_type == "integration"


def test_an_invalid_api_key_never_falls_back_to_the_cookie(world):
    _, use_case, _, _, machine = world
    with pytest.raises(UnauthorizedException):
        use_case.execute(f"{machine.id}.wrong", "session", optional=True)


@pytest.mark.parametrize("api_key", ["no-dot", "not-a-uuid.secret", f"{uuid4()}.{_SECRET}"])
def test_malformed_or_unknown_api_keys_are_unauthorized(world, api_key):
    _, use_case, *_ = world
    with pytest.raises(UnauthorizedException):
        use_case.execute(api_key, None)


def test_an_api_key_of_a_human_agent_is_rejected(world):
    uow, use_case, _, human, _ = world
    human.hashed_password = FakePasswordHasher().hash(_SECRET)
    with pytest.raises(UnauthorizedException):
        use_case.execute(f"{human.id}.{_SECRET}", None)


def test_an_unknown_or_revoked_session_is_unauthorized_even_when_optional(world):
    uow, use_case, *_ = world
    with pytest.raises(UnauthorizedException):
        use_case.execute(None, "forged", optional=True)
    uow.sessions.revoke(sha256(b"session").hexdigest(), datetime.now(timezone.utc))
    with pytest.raises(UnauthorizedException):
        use_case.execute(None, "session")


def test_an_inactive_agent_is_unauthorized(world):
    _, use_case, _, human, _ = world
    human.is_active = False
    with pytest.raises(UnauthorizedException):
        use_case.execute(None, "session")


def test_no_credential_is_unauthorized_unless_optional(world):
    _, use_case, *_ = world
    with pytest.raises(UnauthorizedException):
        use_case.execute(None, None)
    assert use_case.execute(None, None, optional=True) is None


def test_agents_of_a_suspended_tenant_are_unauthorized_even_if_still_active(world):
    """Not checked by the backend, which relied only on deactivating the agents:
    one reactivated on its own afterwards would get back in."""
    uow, use_case, tenant, _, machine = world
    tenant.deactivate()
    uow.tenants.save(tenant)
    with pytest.raises(UnauthorizedException):
        use_case.execute(None, "session")
    with pytest.raises(UnauthorizedException):
        use_case.execute(f"{machine.id}.{_SECRET}", None)


def test_the_platform_admin_has_no_tenant_to_check(world):
    uow, use_case, *_ = world
    admin = uow.agents.save(Agent.create("Root", "root@platform.test", role=AgentRole.ADMIN))
    now = datetime.now(timezone.utc)
    uow.sessions.save(AuthSession(sha256(b"admin").hexdigest(), admin.id.value, now, now + timedelta(hours=1)))
    assert use_case.execute(None, "admin").agent is admin


def test_an_agent_whose_tenant_row_is_missing_is_still_accepted(world):
    """Legacy data: agents copied before their tenant row exists, as the backend allowed.
    sync_tenants backfills the row; refusing here would lock those agents out until then."""
    uow, use_case, *_ = world
    orphan = uow.agents.save(Agent.create("Olga", "olga@gone.test", role=AgentRole.AGENT, tenant_id=uuid4()))
    now = datetime.now(timezone.utc)
    uow.sessions.save(AuthSession(sha256(b"orphan").hexdigest(), orphan.id.value, now, now + timedelta(hours=1)))
    assert use_case.execute(None, "orphan").agent is orphan
