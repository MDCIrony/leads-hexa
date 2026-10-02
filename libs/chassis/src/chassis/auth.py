"""Internal token: signing, key publication and verification (ADR-0032).

Every service verifies with this same code, so a rule tightened here is
tightened everywhere at once."""
import base64
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ALGORITHM = "EdDSA"
_REQUIRED_CLAIMS = ["iss", "aud", "sub", "iat", "exp", "jti"]


class TokenError(Exception):
    """The token cannot be trusted. Callers map it to 401 without detail."""


@dataclass(frozen=True)
class Claims:
    sub: str
    tid: Optional[str]
    role: str
    ptype: str
    aud: str
    jti: str
    exp: int


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Ed25519Signer:
    def __init__(self, kid: str, private_key: Ed25519PrivateKey) -> None:
        self.kid = kid
        self._key = private_key

    @classmethod
    def from_seed(cls, kid: str, seed_b64url: str) -> "Ed25519Signer":
        seed = _b64url_decode(seed_b64url)
        if len(seed) != 32:
            raise ValueError(f"signing key {kid!r} must be a 32-byte Ed25519 seed")
        return cls(kid, Ed25519PrivateKey.from_private_bytes(seed))

    def sign(self, claims: dict) -> str:
        return jwt.encode(claims, self._key, algorithm=ALGORITHM, headers={"kid": self.kid})

    def public_jwk(self) -> dict:
        raw = self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return {"kty": "OKP", "crv": "Ed25519", "x": _b64url(raw), "kid": self.kid,
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


class JwksCache:
    def __init__(self, fetch: Callable[[], dict], min_refresh_seconds: float = 10.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._fetch = fetch
        self._min_refresh = min_refresh_seconds
        self._clock = clock
        self._keys: dict[str, Ed25519PublicKey] = {}
        self._fetched_at: Optional[float] = None
        self._lock = threading.Lock()

    def key(self, kid: str) -> Ed25519PublicKey:
        with self._lock:
            if kid not in self._keys and self._may_refresh():
                self._refresh()
            try:
                return self._keys[kid]
            except KeyError:
                raise TokenError("unknown signing key") from None

    def _may_refresh(self) -> bool:
        # Rate-limited: a flood of tokens with invented kids must not turn
        # into a flood of requests against the JWKS endpoint.
        return self._fetched_at is None or self._clock() - self._fetched_at >= self._min_refresh

    def _refresh(self) -> None:
        self._fetched_at = self._clock()
        try:
            document = self._fetch()
        except Exception as error:
            raise TokenError("signing keys unavailable") from error
        self._keys = {
            jwk["kid"]: Ed25519PublicKey.from_public_bytes(_b64url_decode(jwk["x"]))
            for jwk in document.get("keys", [])
            if jwk.get("kty") == "OKP" and jwk.get("crv") == "Ed25519" and "kid" in jwk
        }


def http_jwks(url: str, timeout: float = 2.0) -> Callable[[], dict]:
    client = httpx.Client(timeout=timeout)

    def fetch() -> dict:
        response = client.get(url)
        response.raise_for_status()
        return response.json()

    return fetch


class TokenVerifier:
    def __init__(self, jwks: JwksCache, *, issuer: str, audience: str, leeway: int = 5) -> None:
        self._jwks = jwks
        self._issuer = issuer
        self._audience = audience
        self._leeway = leeway

    def verify(self, token: str) -> Claims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise TokenError("malformed token") from error
        kid = header.get("kid")
        # Checked before any key is chosen: the algorithm is ours to fix,
        # never the token's to declare.
        if header.get("alg") != ALGORITHM or not isinstance(kid, str):
            raise TokenError("unexpected token header")
        key = self._jwks.key(kid)
        try:
            payload = jwt.decode(
                token, key, algorithms=[ALGORITHM], audience=self._audience,
                issuer=self._issuer, leeway=self._leeway,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as error:
            raise TokenError("invalid token") from error
        return Claims(
            sub=str(payload["sub"]), tid=payload.get("tid"), role=str(payload.get("role", "")),
            ptype=str(payload.get("ptype", "")), aud=str(payload["aud"]),
            jti=str(payload["jti"]), exp=int(payload["exp"]),
        )
