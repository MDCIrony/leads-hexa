import threading
import time
from typing import Callable, Optional

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from chassis.auth.claims import TokenError
from chassis.auth.signing import b64url_decode


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
        try:
            keys = {
                jwk["kid"]: Ed25519PublicKey.from_public_bytes(b64url_decode(jwk["x"]))
                for jwk in document.get("keys", [])
                if jwk.get("kty") == "OKP" and jwk.get("crv") == "Ed25519" and "kid" in jwk
            }
        except Exception as error:
            # A bad document must not wipe the keys already trusted.
            raise TokenError("signing keys unavailable") from error
        self._keys = keys


def http_jwks(url: str, timeout: float = 2.0) -> Callable[[], dict]:
    client = httpx.Client(timeout=timeout)

    def fetch() -> dict:
        response = client.get(url)
        response.raise_for_status()
        return response.json()

    return fetch
