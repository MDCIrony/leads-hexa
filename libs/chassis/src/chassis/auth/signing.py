import base64
import re

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ALGORITHM = "EdDSA"
_SEED_ALPHABET = re.compile(r"[A-Za-z0-9_-]+")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Ed25519Signer:
    def __init__(self, kid: str, private_key: Ed25519PrivateKey) -> None:
        self.kid = kid
        self._key = private_key

    @classmethod
    def from_seed(cls, kid: str, seed_b64url: str) -> "Ed25519Signer":
        # Strict: the lenient decoder drops stray characters, so a typo would
        # silently produce a different key instead of failing at startup.
        if not _SEED_ALPHABET.fullmatch(seed_b64url):
            raise ValueError(f"signing key {kid!r} is not base64url")
        seed = b64url_decode(seed_b64url)
        if len(seed) != 32:
            raise ValueError(f"signing key {kid!r} must be a 32-byte Ed25519 seed")
        return cls(kid, Ed25519PrivateKey.from_private_bytes(seed))

    def sign(self, claims: dict) -> str:
        return jwt.encode(claims, self._key, algorithm=ALGORITHM, headers={"kid": self.kid})

    def public_jwk(self) -> dict:
        raw = self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return {"kty": "OKP", "crv": "Ed25519", "x": b64url(raw), "kid": self.kid,
                "alg": ALGORITHM, "use": "sig"}


def load_signers(spec: str) -> list[Ed25519Signer]:
    """`kid=seed[,kid=seed]`: the first one signs, all of them are published,
    which is what lets a rotation overlap the old key's last tokens."""
    signers: list[Ed25519Signer] = []
    for entry in (part.strip() for part in spec.split(",")):
        if not entry:
            continue
        kid, sep, seed = entry.partition("=")
        if not sep or not kid.strip() or not seed.strip():
            raise ValueError("SIGNING_KEYS entries must look like kid=seed")
        signers.append(Ed25519Signer.from_seed(kid.strip(), seed.strip()))
    if not signers:
        raise ValueError("SIGNING_KEYS is required and has no default")
    if len({s.kid for s in signers}) != len(signers):
        raise ValueError("SIGNING_KEYS has a repeated kid")
    return signers
