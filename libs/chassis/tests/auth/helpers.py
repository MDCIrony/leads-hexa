import time
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from chassis.auth import AUDIENCE, ISSUER, Ed25519Signer, JwksCache, TokenVerifier


def claims(**overrides):
    now = int(time.time())
    base = {"iss": ISSUER, "aud": AUDIENCE, "sub": str(uuid.uuid4()), "tid": str(uuid.uuid4()),
            "role": "MANAGER", "ptype": "human", "iat": now, "exp": now + 60,
            "jti": str(uuid.uuid4())}
    base.update(overrides)
    return base


def signer(kid="k1"):
    return Ed25519Signer(kid, Ed25519PrivateKey.generate())


def verifier_for(fetch, **cache_options):
    return TokenVerifier(JwksCache(fetch, **cache_options), issuer=ISSUER, audience=AUDIENCE)


def verifier(*signers):
    return verifier_for(lambda: {"keys": [s.public_jwk() for s in signers]})


class FakeJwks:
    """A `fetch` double: counts calls, serves `document`, raises when `error` is set."""

    def __init__(self, *signers, error=None):
        self.document = {"keys": [s.public_jwk() for s in signers]}
        self.error = error
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.document


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now
