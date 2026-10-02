import time
from uuid import uuid4

from chassis.auth import Ed25519Signer
from domain.entities.agent import Agent


class InternalTokenIssuer:
    """Mints the internal token the gateway forwards (ADR-0032). Lives in the
    monolith only until identity is extracted (F3)."""

    ISSUER = "identity"
    AUDIENCE = "lead-router"

    def __init__(self, signer: Ed25519Signer, ttl_seconds: int = 60) -> None:
        self._signer = signer
        self._ttl = ttl_seconds

    def issue(self, agent: Agent, principal_type: str) -> str:
        now = int(time.time())
        return self._signer.sign({
            "iss": self.ISSUER, "aud": self.AUDIENCE, "sub": str(agent.id),
            "tid": str(agent.tenant_id) if agent.tenant_id else None,
            "role": agent.role.value, "ptype": principal_type,
            "iat": now, "exp": now + self._ttl, "jti": str(uuid4()),
        })
