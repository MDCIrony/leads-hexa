import pytest

from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from domain.exceptions import UnauthorizedException
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService

_SECRET = "test-secret-do-not-use-in-production"


def test_adapter_satisfies_the_port():
    assert isinstance(JwtTokenService(secret=_SECRET), TokenServicePort)


def test_issued_token_round_trips_its_claims():
    service = JwtTokenService(secret=_SECRET)
    claims = TokenClaims(agent_id="a-1", role="MANAGER", tenant_id="t-1")
    assert service.verify(service.issue(claims)) == claims


def test_null_tenant_survives_the_round_trip():
    service = JwtTokenService(secret=_SECRET)
    claims = TokenClaims(agent_id="a-1", role="ADMIN", tenant_id=None)
    assert service.verify(service.issue(claims)).tenant_id is None


def test_tampered_token_is_rejected():
    service = JwtTokenService(secret=_SECRET)
    token = service.issue(TokenClaims(agent_id="a-1", role="AGENT", tenant_id="t-1"))
    with pytest.raises(UnauthorizedException):
        service.verify(token + "x")


def test_token_signed_with_another_secret_is_rejected():
    issued = JwtTokenService(secret="one-secret").issue(
        TokenClaims(agent_id="a-1", role="AGENT", tenant_id="t-1")
    )
    with pytest.raises(UnauthorizedException):
        JwtTokenService(secret="another-secret").verify(issued)


def test_expired_token_is_rejected():
    service = JwtTokenService(secret=_SECRET, expires_minutes=-1)
    token = service.issue(TokenClaims(agent_id="a-1", role="AGENT", tenant_id="t-1"))
    with pytest.raises(UnauthorizedException):
        service.verify(token)


def test_garbage_is_rejected_as_unauthorized_not_as_a_library_error():
    """A malformed token must surface as a domain exception, so the API layer
    has one thing to catch instead of every PyJWT error type."""
    with pytest.raises(UnauthorizedException):
        JwtTokenService(secret=_SECRET).verify("not-a-token")
