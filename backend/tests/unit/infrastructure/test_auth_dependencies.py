import time
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from chassis.auth import Ed25519Signer, JwksCache, TokenVerifier

from domain.entities.agent import Agent
from domain.entities.auth_session import AuthSession
from domain.exceptions import DomainException, ForbiddenException, UnauthorizedException
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.api.exception_handlers import STATUS_BY_ERROR_CODE
from infrastructure.adapters.input.api.dependencies import (
    get_optional_human_principal,
    get_optional_principal,
    get_principal,
    get_request_context,
    require_manager_or_integration,
    resolve_current_agent,
    resolve_integration_agent,
)
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT_A = uuid4()
_HASHER = FakePasswordHasher()


_SIGNER = Ed25519Signer.from_seed("unit-1", "We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk")


class _StubContainer:
    """Only what the bearer dependencies read off the real Container."""

    token_verifier = TokenVerifier(
        JwksCache(lambda: {"keys": [_SIGNER.public_jwk()]}), issuer="identity", audience="lead-router",
    )


def _bearer(role="MANAGER", ptype="human", tid=str(_TENANT_A), sub=None, exp_in=60, signer=_SIGNER) -> str:
    now = int(time.time())
    return signer.sign({
        "iss": "identity", "aud": "lead-router", "sub": sub or str(uuid4()), "tid": tid,
        "role": role, "ptype": ptype, "iat": now, "exp": now + exp_in, "jti": str(uuid4()),
    })


def _request(token=None, authorization=None):
    value = authorization if authorization is not None else (f"Bearer {token}" if token is not None else None)
    return SimpleNamespace(headers={} if value is None else {"authorization": value})


def _principal(token):
    return get_principal(_request(token), _StubContainer())


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
    from hashlib import sha256
    from datetime import datetime, timedelta, timezone
    from domain.entities.auth_session import AuthSession
    token = "opaque-session"
    uow = _uow_with(agent)
    uow.sessions.save(AuthSession(sha256(token.encode()).hexdigest(), agent.id.value, datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1)))
    return token


def test_valid_token_resolves_the_agent():
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    uow = _uow_with(agent)
    from hashlib import sha256
    from datetime import datetime, timedelta, timezone
    from domain.entities.auth_session import AuthSession
    token = "opaque-session"
    uow.sessions.save(AuthSession(sha256(token.encode()).hexdigest(), agent.id.value, datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1)))
    resolved = resolve_current_agent(token=token, uow=uow)
    assert str(resolved.id) == str(agent.id)


def test_malformed_token_is_unauthorized():
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(token="garbage", uow=_uow_with(agent))


def test_deactivated_agent_is_unauthorized_even_with_a_valid_token():
    """Identity is revalidated against the database on every request, so
    deactivating an account cuts an outstanding token immediately."""
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    uow = _uow_with(agent)
    token = "opaque-session"
    uow.sessions.save(AuthSession(sha256(token.encode()).hexdigest(), agent.id.value, datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1)))
    agent.is_active = False
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(token=token, uow=uow)


def test_expired_session_is_unauthorized_even_with_an_active_agent():
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    uow = _uow_with(agent)
    token = "opaque-session"
    uow.sessions.save(AuthSession(sha256(token.encode()).hexdigest(), agent.id.value, datetime.now(timezone.utc) - timedelta(hours=2), datetime.now(timezone.utc) - timedelta(hours=1)))
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(token=token, uow=uow)


def test_revoked_session_is_unauthorized_even_before_expiry():
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    uow = _uow_with(agent)
    token = "opaque-session"
    uow.sessions.save(AuthSession(sha256(token.encode()).hexdigest(), agent.id.value, datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1)))
    uow.sessions.revoke(sha256(token.encode()).hexdigest(), datetime.now(timezone.utc))
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(token=token, uow=uow)


def test_well_formed_but_unknown_token_is_unauthorized():
    agent = Agent.create("M", "m@test.com", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(token="never-issued-session-value", uow=_uow_with(agent))


def test_sales_agent_is_refused_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    context = get_request_context(_principal(_bearer(role="AGENT")))
    with pytest.raises(ForbiddenException):
        require_organization_manager(context=context)


def test_manager_is_allowed_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    context = get_request_context(_principal(_bearer()))
    assert require_organization_manager(context=context) is context


def test_resolve_integration_agent_with_a_well_formed_key_resolves_the_agent():
    agent = _integration_agent()
    api_key = f"{agent.id}.s3cr3t"

    resolved = resolve_integration_agent(api_key, uow=_uow_with(agent), password_hasher=_HASHER)

    assert str(resolved.id) == str(agent.id)
    assert str(resolved.tenant_id) == str(_TENANT_A)


def test_resolve_integration_agent_rejects_a_key_with_no_dot():
    agent = _integration_agent()
    with pytest.raises(UnauthorizedException):
        resolve_integration_agent("no-dot-here", uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_agent_rejects_a_non_uuid_agent_id():
    agent = _integration_agent()
    with pytest.raises(UnauthorizedException):
        resolve_integration_agent("not-a-uuid.s3cr3t", uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_agent_rejects_an_unknown_agent():
    agent = _integration_agent()
    api_key = f"{uuid4()}.s3cr3t"
    with pytest.raises(UnauthorizedException):
        resolve_integration_agent(api_key, uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_agent_rejects_an_inactive_agent():
    agent = _integration_agent(is_active=False)
    api_key = f"{agent.id}.s3cr3t"
    with pytest.raises(UnauthorizedException):
        resolve_integration_agent(api_key, uow=_uow_with(agent), password_hasher=_HASHER)


def test_resolve_integration_agent_rejects_a_non_integration_role():
    manager = Agent.create(
        "M", "m2@test.com", role=AgentRole.MANAGER, hashed_password=_HASHER.hash("s3cr3t"), tenant_id=_TENANT_A
    )
    api_key = f"{manager.id}.s3cr3t"
    with pytest.raises(UnauthorizedException):
        resolve_integration_agent(api_key, uow=_uow_with(manager), password_hasher=_HASHER)


def test_resolve_integration_agent_rejects_a_secret_that_does_not_verify():
    agent = _integration_agent()
    api_key = f"{agent.id}.wrong-secret"
    with pytest.raises(UnauthorizedException):
        resolve_integration_agent(api_key, uow=_uow_with(agent), password_hasher=_HASHER)


def test_a_valid_human_bearer_yields_the_principal_and_its_context():
    sub = str(uuid4())
    principal = _principal(_bearer(sub=sub))

    context = get_request_context(principal)

    assert str(principal.id) == sub
    assert principal.role == AgentRole.MANAGER
    assert principal.principal_type == "human"
    assert str(context.tenant_id) == str(_TENANT_A)


def test_a_platform_admin_bearer_has_no_tenant():
    principal = _principal(_bearer(role="ADMIN", tid=None))
    assert principal.tenant_id is None


def test_an_integration_bearer_is_refused_by_get_request_context():
    principal = _principal(_bearer(role="INTEGRATION", ptype="integration"))
    with pytest.raises(UnauthorizedException):
        get_request_context(principal)


@pytest.mark.parametrize("token", ["garbage", "a.b.c", _bearer(exp_in=-3600)])
def test_an_invalid_or_expired_bearer_is_unauthorized(token):
    with pytest.raises(UnauthorizedException):
        _principal(token)


def test_a_bearer_with_an_unknown_role_is_unauthorized():
    with pytest.raises(UnauthorizedException):
        _principal(_bearer(role="SUPERUSER"))


def test_unreachable_signing_keys_are_a_503_not_a_401():
    def _unreachable() -> dict:
        raise ConnectionError("jwks down")

    container = SimpleNamespace(token_verifier=TokenVerifier(
        JwksCache(_unreachable), issuer="identity", audience="lead-router",
    ))

    with pytest.raises(DomainException) as raised:
        get_principal(_request(_bearer()), container)

    assert raised.value.error_code == "SERVICE_UNAVAILABLE"
    assert STATUS_BY_ERROR_CODE[raised.value.error_code] == 503


def test_a_bearer_with_a_non_uuid_subject_is_unauthorized():
    with pytest.raises(UnauthorizedException):
        _principal(_bearer(sub="not-a-uuid"))


def test_a_missing_or_empty_bearer_is_unauthorized():
    for request in (_request(), _request(authorization="Bearer "), _request(authorization="Bearer")):
        with pytest.raises(UnauthorizedException):
            get_principal(request, _StubContainer())


def test_another_authorization_scheme_is_unauthorized():
    with pytest.raises(UnauthorizedException):
        get_principal(_request(authorization="Basic dXNlcjpwYXNz"), _StubContainer())


def test_optional_principal_is_none_only_without_a_bearer():
    assert get_optional_principal(_request(), _StubContainer()) is None
    assert get_optional_principal(_request(authorization="Bearer "), _StubContainer()) is None
    with pytest.raises(UnauthorizedException):
        get_optional_principal(_request("garbage"), _StubContainer())


def test_optional_principal_resolves_a_valid_bearer():
    principal = get_optional_principal(_request(_bearer()), _StubContainer())
    assert principal is not None and principal.role == AgentRole.MANAGER


def test_manager_or_integration_accepts_an_integration_with_its_own_tenant():
    context = require_manager_or_integration(_principal(_bearer(role="INTEGRATION", ptype="integration")))
    assert str(context.tenant_id) == str(_TENANT_A)


def test_manager_or_integration_accepts_a_manager():
    context = require_manager_or_integration(_principal(_bearer()))
    assert str(context.tenant_id) == str(_TENANT_A)


def test_manager_or_integration_refuses_a_sales_agent():
    with pytest.raises(ForbiddenException):
        require_manager_or_integration(_principal(_bearer(role="AGENT")))


def test_manager_or_integration_without_a_bearer_is_unauthorized():
    with pytest.raises(UnauthorizedException):
        require_manager_or_integration(get_principal(_request(), _StubContainer()))


@pytest.mark.parametrize("role,ptype", [
    ("MANAGER", "machine"),
    ("MANAGER", ""),
    ("INTEGRATION", "human"),
    ("MANAGER", "integration"),
    ("ADMIN", "integration"),
])
def test_an_incoherent_role_and_principal_type_is_unauthorized(role, ptype):
    with pytest.raises(UnauthorizedException):
        _principal(_bearer(role=role, ptype=ptype))


def test_optional_human_principal_refuses_a_machine_principal():
    token = _bearer(role="INTEGRATION", ptype="integration")
    with pytest.raises(UnauthorizedException):
        get_optional_human_principal(get_optional_principal(_request(token), _StubContainer()))


def test_optional_human_principal_passes_none_and_humans_through():
    assert get_optional_human_principal(None) is None
    human = _principal(_bearer())
    assert get_optional_human_principal(human) is human
