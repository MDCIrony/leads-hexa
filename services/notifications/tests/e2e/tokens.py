import time
from uuid import UUID, uuid4

from chassis.auth import AUDIENCE, ISSUER, Ed25519Signer
from chassis.auth.signing import b64url

KID = "test-key"
SIGNER = Ed25519Signer.from_seed(KID, b64url(bytes([1]) * 32))
# Same kid, different key: the signature is what must fail, not the lookup.
FOREIGN_SIGNER = Ed25519Signer.from_seed(KID, b64url(bytes([2]) * 32))


def jwks() -> dict:
    return {"keys": [SIGNER.public_jwk()]}


def mint_token(
    agent_id: UUID | str | None = None,
    tenant_id: UUID | None = None,
    role: str = "AGENT",
    ptype: str = "human",
    signer: Ed25519Signer = SIGNER,
) -> str:
    now = int(time.time())
    return signer.sign({
        "iss": ISSUER, "aud": AUDIENCE, "sub": str(agent_id or uuid4()),
        "tid": str(tenant_id) if tenant_id else None,
        "role": role, "ptype": ptype, "iat": now, "exp": now + 60, "jti": uuid4().hex,
    })


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
