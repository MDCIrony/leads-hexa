from uuid import uuid4

import jwt
import pytest
from chassis.auth import AUDIENCE, ISSUER, Ed25519Signer, JwksCache, TokenVerifier

from domain.agents.agent import Agent
from domain.value_objects.agent_role import AgentRole
from infrastructure.security.internal_token_issuer import InternalTokenIssuer

_SIGNER = Ed25519Signer.from_seed("unit-1", "We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk")
_ISSUER = InternalTokenIssuer(_SIGNER)
_VERIFIER = TokenVerifier(JwksCache(lambda: {"keys": [_SIGNER.public_jwk()]}), issuer=ISSUER, audience=AUDIENCE)


def _agent(role: AgentRole, tenant_id=None) -> Agent:
    return Agent.create("Subject", f"{uuid4().hex[:8]}@a.invalid", role=role, tenant_id=tenant_id)


@pytest.mark.parametrize("role,ptype", [
    (AgentRole.MANAGER, "human"),
    (AgentRole.AGENT, "human"),
    (AgentRole.INTEGRATION, "integration"),
])
def test_token_carries_the_agent_identity_and_tenant(role, ptype):
    agent = _agent(role, tenant_id=uuid4())

    claims = _VERIFIER.verify(_ISSUER.issue(agent, ptype))

    assert claims.sub == str(agent.id)
    assert claims.tid == str(agent.tenant_id)
    assert claims.role == role.value
    assert claims.ptype == ptype


def test_platform_admin_token_has_no_tenant():
    claims = _VERIFIER.verify(_ISSUER.issue(_agent(AgentRole.ADMIN), "human"))

    assert claims.tid is None
    assert claims.role == "ADMIN"


def test_token_lives_sixty_seconds_and_names_its_key():
    token = _ISSUER.issue(_agent(AgentRole.MANAGER, uuid4()), "human")
    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["exp"] - payload["iat"] == 60
    assert payload["iss"] == "identity"
    assert payload["aud"] == "lead-router"
    assert jwt.get_unverified_header(token)["kid"] == "unit-1"


def test_every_emission_gets_its_own_jti():
    agent = _agent(AgentRole.MANAGER, uuid4())

    assert _VERIFIER.verify(_ISSUER.issue(agent, "human")).jti != _VERIFIER.verify(_ISSUER.issue(agent, "human")).jti
