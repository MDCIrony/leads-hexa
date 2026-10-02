import time
from uuid import uuid4

from chassis.auth import AUDIENCE, ISSUER, Ed25519Signer

from domain.agents.agent import Agent


class InternalTokenIssuer:
    """Mints the internal token the gateway forwards with every request (ADR-0032)."""

    TTL_SECONDS = 60

    def __init__(self, signer: Ed25519Signer) -> None:
        self._signer = signer

    def issue(self, agent: Agent, principal_type: str) -> str:
        now = int(time.time())
        return self._signer.sign({
            "iss": ISSUER, "aud": AUDIENCE, "sub": str(agent.id),
            "tid": str(agent.tenant_id) if agent.tenant_id else None,
            "role": agent.role.value, "ptype": principal_type,
            "iat": now, "exp": now + self.TTL_SECONDS, "jti": str(uuid4()),
        })
