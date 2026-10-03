"""What identity signs, minted in-process: the suite runs no identity and no gateway."""
import time
from uuid import UUID, uuid4

from chassis.auth import AUDIENCE, ISSUER, Ed25519Signer
from chassis.auth.signing import b64url

SIGNER = Ed25519Signer.from_seed("test-key", b64url(bytes([1]) * 32))


def jwks() -> dict:
    return {"keys": [SIGNER.public_jwk()]}


def mint_token(
    agent_id: UUID | str | None = None,
    tenant_id: UUID | str | None = None,
    role: str = "MANAGER",
    ptype: str = "human",
    signer: Ed25519Signer = SIGNER,
) -> str:
    now = int(time.time())
    return signer.sign({
        "iss": ISSUER, "aud": AUDIENCE, "sub": str(agent_id or uuid4()),
        "tid": str(tenant_id) if tenant_id else None,
        "role": role, "ptype": ptype, "iat": now, "exp": now + 60, "jti": uuid4().hex,
    })


def mint_service_token(sub: str = "intake", audience: str = "lead-core") -> str:
    """What identity signs for a service calling another (/internal/v1/*)."""
    now = int(time.time())
    return SIGNER.sign({"iss": ISSUER, "aud": audience, "sub": sub, "ptype": "service",
                        "iat": now, "exp": now + 60, "jti": uuid4().hex})
