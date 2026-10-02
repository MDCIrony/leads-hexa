"""Bearers as the gateway or a calling service would send them, signed with the key
conftest gives identity, for tests that skip the introspection on purpose."""
import time
from uuid import UUID, uuid4

from chassis.auth import AUDIENCE, ISSUER, SERVICE_PTYPE, Ed25519Signer, load_signers
from chassis.auth.signing import b64url

from tests import environment

SIGNER = load_signers(environment.SIGNING_KEYS)[0]
# Same kid, different key: the signature is what must fail, not the lookup.
FOREIGN_SIGNER = Ed25519Signer.from_seed(SIGNER.kid, b64url(bytes([2]) * 32))


def _claims(**claims) -> dict:
    now = int(time.time())
    return {"iss": ISSUER, "iat": now, "exp": now + 60, "jti": uuid4().hex, **claims}


def mint_token(
    agent_id: UUID | str | None = None,
    tenant_id: UUID | str | None = None,
    role: str = "MANAGER",
    ptype: str = "human",
    signer: Ed25519Signer = SIGNER,
) -> str:
    return signer.sign(_claims(
        aud=AUDIENCE, sub=str(agent_id or uuid4()), tid=str(tenant_id) if tenant_id else None,
        role=role, ptype=ptype,
    ))


def mint_service_token(
    caller: str = environment.SERVICE_CLIENT_ID,
    audience: str = "identity",
    ptype: str = SERVICE_PTYPE,
    signer: Ed25519Signer = SIGNER,
) -> str:
    return signer.sign(_claims(sub=caller, aud=audience, ptype=ptype))


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
