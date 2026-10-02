"""Contract with chassis: what identity issues is what every service's verifier accepts."""
import hashlib
from uuid import uuid4

import jwt
import pytest
from chassis.auth import AUDIENCE, ISSUER, Ed25519Signer, JwksCache, ServiceTokenVerifier, TokenError, TokenVerifier

from domain.agents.agent import Agent
from domain.exceptions import UnauthorizedException
from domain.value_objects.agent_role import AgentRole
from infrastructure.security.internal_token_issuer import InternalTokenIssuer
from infrastructure.security.service_clients import ServiceClients, parse_service_clients
from infrastructure.security.service_token_issuer import ServiceTokenIssuer

_SECRET = "core-secret"
_SIGNER = Ed25519Signer.from_seed("unit-1", "We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk")
_CLIENTS = ServiceClients(parse_service_clients(
    f"lead-core:identity|intake:{hashlib.sha256(_SECRET.encode()).hexdigest()}"
))
_ISSUER = ServiceTokenIssuer(_SIGNER, _CLIENTS)
_KEYS = JwksCache(lambda: {"keys": [_SIGNER.public_jwk()]})
_SERVICE_VERIFIER = ServiceTokenVerifier(_KEYS, audience="identity")
_HUMAN_VERIFIER = TokenVerifier(_KEYS, issuer=ISSUER, audience=AUDIENCE)


def test_the_service_verifier_accepts_the_token_for_its_audience():
    claims = _SERVICE_VERIFIER.verify(_ISSUER.issue("lead-core", _SECRET, "identity"), {"lead-core"})

    assert (claims.sub, claims.aud) == ("lead-core", "identity")


def test_the_claims_and_lifetime_are_the_documented_ones():
    token = _ISSUER.issue("lead-core", _SECRET, "intake")
    payload = jwt.decode(token, options={"verify_signature": False})

    assert {key: payload[key] for key in ("iss", "sub", "aud", "ptype")} == {
        "iss": "identity", "sub": "lead-core", "aud": "intake", "ptype": "service",
    }
    assert payload["exp"] - payload["iat"] == ServiceTokenIssuer.TTL_SECONDS == 300
    assert payload["jti"]
    assert jwt.get_unverified_header(token)["kid"] == "unit-1"


def test_a_service_token_for_another_audience_or_caller_is_refused():
    with pytest.raises(TokenError):
        _SERVICE_VERIFIER.verify(_ISSUER.issue("lead-core", _SECRET, "intake"), {"lead-core"})
    with pytest.raises(TokenError):
        _SERVICE_VERIFIER.verify(_ISSUER.issue("lead-core", _SECRET, "identity"), {"intake"})


def test_a_human_token_opens_the_human_verifier_and_never_the_service_one():
    agent = Agent.create("Ana", "ana@acme.test", role=AgentRole.MANAGER, tenant_id=uuid4())
    human = InternalTokenIssuer(_SIGNER).issue(agent, "human")

    assert _HUMAN_VERIFIER.verify(human).sub == str(agent.id)
    with pytest.raises(TokenError):
        _SERVICE_VERIFIER.verify(human, {str(agent.id)})


def test_a_service_token_never_opens_the_human_verifier():
    with pytest.raises(TokenError):
        _HUMAN_VERIFIER.verify(_ISSUER.issue("lead-core", _SECRET, "identity"))


@pytest.mark.parametrize("client_id,secret,audience", [
    ("lead-core", "wrong", "identity"),
    ("unknown", _SECRET, "identity"),
    ("lead-core", _SECRET, "lead-core"),
])
def test_bad_credentials_get_one_message_that_carries_no_secret(client_id, secret, audience):
    with pytest.raises(UnauthorizedException) as raised:
        _ISSUER.issue(client_id, secret, audience)

    assert raised.value.message == "Invalid service credentials"
    assert raised.value.error_code == "UNAUTHORIZED"
