import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from chassis.auth import Ed25519Signer, JwksCache, TokenVerifier

from domain.exceptions import DomainException, ForbiddenException, UnauthorizedException
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.api.exception_handlers import STATUS_BY_ERROR_CODE
from infrastructure.adapters.input.api.dependencies import (
    get_principal,
    get_request_context,
    require_manager_or_integration,
)

_TENANT_A = uuid4()


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


def test_sales_agent_is_refused_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    context = get_request_context(_principal(_bearer(role="AGENT")))
    with pytest.raises(ForbiddenException):
        require_organization_manager(context=context)


def test_manager_is_allowed_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    context = get_request_context(_principal(_bearer()))
    assert require_organization_manager(context=context) is context


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
