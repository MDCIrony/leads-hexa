import logging
import threading
import time
from typing import Callable, Optional

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from chassis.auth.claims import KeysUnavailable, TokenError
from chassis.auth.signing import b64url_decode

logger = logging.getLogger(__name__)


class JwksCache:
    """Public keys by `kid`, refreshed from the JWKS endpoint.

    A refresh replaces the whole set, so a key that is no longer published
    stops being trusted (that is how a rotation retires the old key). A failed
    refresh keeps what was already trusted: an expired key beats an outage."""

    def __init__(self, fetch: Callable[[], dict], min_refresh_seconds: float = 10.0,
                 max_age_seconds: float = 60.0, cold_retry_seconds: float = 1.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._fetch = fetch
        self._min_refresh = min_refresh_seconds
        self._max_age = max_age_seconds
        self._cold_retry = cold_retry_seconds
        self._clock = clock
        # One tuple, replaced whole: the lock-free reader never sees keys from
        # one refresh paired with the load time of another.
        self._loaded: Optional[tuple[dict[str, Ed25519PublicKey], float]] = None
        self._attempted_at: Optional[float] = None
        self._last_failed = False
        self._lock = threading.Lock()

    def key(self, kid: str) -> Ed25519PublicKey:
        found = self._fresh(kid)
        if found is not None:
            return found
        with self._lock:
            found = self._fresh(kid)
            if found is not None:
                return found
            if not self._may_refresh():
                return self._known_or_unavailable(kid)
            self._attempted_at = self._clock()
            try:
                self._loaded = (self._load(), self._clock())
                self._last_failed = False
            except Exception as error:
                self._last_failed = True
                logger.warning("JWKS refresh failed: %s", error)
                return self._known_or_unavailable(kid)
        keys = self._loaded[0]
        if kid in keys:
            return keys[kid]
        if not keys:
            raise KeysUnavailable("signing keys unavailable")
        # Only a document fetched in this very call proves the kid is not published.
        raise TokenError("unknown signing key")

    def _fresh(self, kid: str) -> Optional[Ed25519PublicKey]:
        loaded = self._loaded
        if loaded is None or self._clock() - loaded[1] >= self._max_age:
            return None
        return loaded[0].get(kid)

    def _known_or_unavailable(self, kid: str) -> Ed25519PublicKey:
        keys = self._loaded[0] if self._loaded else {}
        if kid in keys:
            return keys[kid]
        # Not checked against a fresh document: during a rotation the kid may be
        # valid, and a 401 would end the session. Ours to answer, as 503.
        raise KeysUnavailable("signing key cannot be checked yet")

    def _may_refresh(self) -> bool:
        # Rate-limited: a flood of tokens with invented kids must not turn
        # into a flood of requests against the JWKS endpoint. After a failure
        # the short interval applies, so a recovered endpoint is seen quickly.
        if self._attempted_at is None:
            return True
        healthy = not self._last_failed and self._loaded and self._loaded[0]
        interval = self._min_refresh if healthy else self._cold_retry
        return self._clock() - self._attempted_at >= interval

    def _load(self) -> dict[str, Ed25519PublicKey]:
        document = self._fetch()
        return {
            jwk["kid"]: Ed25519PublicKey.from_public_bytes(b64url_decode(jwk["x"]))
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
