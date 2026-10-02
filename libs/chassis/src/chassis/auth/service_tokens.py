"""Service tokens: calls between services with no user behind them (client credentials).

Identity issues them with `ptype=service`, `sub` = the calling service and
`aud` = the service called; each internal route admits only its own callers."""
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Collection, Optional, Protocol

import httpx

from chassis.auth.claims import ISSUER, TokenError
from chassis.auth.jwks import JwksCache
from chassis.auth.verifier import decode

SERVICE_PTYPE = "service"


@dataclass(frozen=True)
class ServiceClaims:
    sub: str
    aud: str
    jti: str
    exp: int


class ServiceTokenUnavailable(Exception):
    """No service token could be obtained. Never carries the client secret."""


class ServiceTokenVerifier:
    def __init__(self, jwks: JwksCache, *, audience: str, leeway: int = 5) -> None:
        self._jwks = jwks
        self._audience = audience
        self._leeway = leeway

    def verify(self, token: str, allowed_callers: Collection[str]) -> ServiceClaims:
        payload = decode(self._jwks, token, issuer=ISSUER, audience=self._audience,
                         leeway=self._leeway)
        # Exact match: a human or integration token must never open an internal route.
        if payload.get("ptype") != SERVICE_PTYPE:
            raise TokenError("not a service token")
        sub = payload["sub"]
        if not isinstance(sub, str) or sub not in allowed_callers:
            raise TokenError("caller not allowed")
        return ServiceClaims(sub=sub, aud=str(payload["aud"]), jti=str(payload["jti"]),
                             exp=int(payload["exp"]))


class _Response(Protocol):
    status_code: int

    def json(self) -> Any: ...


def _http_post(url: str, json: dict) -> httpx.Response:
    return httpx.post(url, json=json, timeout=2.0)


class ServiceTokenClient:
    """Fetches a service token and reuses it until it is about to expire."""

    def __init__(self, token_url: str, client_id: str, client_secret: str, audience: str, *,
                 post: Optional[Callable[..., _Response]] = None,
                 clock: Callable[[], float] = time.time, renew_margin: float = 30) -> None:
        self._url = token_url
        self._client_id = client_id
        self._secret = client_secret
        self._audience = audience
        self._post = post or _http_post
        self._clock = clock
        self._margin = renew_margin
        # (token, expires_at) replaced whole, so the lock-free reader never pairs
        # one token with another's expiry.
        self._cached: Optional[tuple[str, float]] = None
        self._lock = threading.Lock()

    def token(self) -> str:
        cached = self._valid()
        if cached is not None:
            return cached
        with self._lock:
            cached = self._valid()
            if cached is not None:
                return cached
            self._cached = self._fetch()
            return self._cached[0]

    def invalidate(self) -> None:
        """Drops the cached token: the callee refused it (a rotated key, a changed
        client entry), and waiting for its expiry would refuse every call until then."""
        self._cached = None

    def _valid(self) -> Optional[str]:
        cached = self._cached
        if cached is not None and cached[1] - self._clock() > self._margin:
            return cached[0]
        return None

    def _fetch(self) -> tuple[str, float]:
        body = {"client_id": self._client_id, "client_secret": self._secret,
                "audience": self._audience}
        try:
            response = self._post(self._url, json=body)
        except Exception as error:
            # The error's text is not trusted to leave the secret out; only its type travels.
            raise ServiceTokenUnavailable(
                f"token endpoint unreachable: {type(error).__name__}") from None
        if response.status_code != 200:
            raise ServiceTokenUnavailable(f"token endpoint answered {response.status_code}")
        try:
            document = response.json()
        except ValueError:
            document = None
        token = document.get("access_token") if isinstance(document, dict) else None
        expires_in = document.get("expires_in") if isinstance(document, dict) else None
        if not isinstance(token, str) or isinstance(expires_in, bool) or not isinstance(expires_in, int):
            raise ServiceTokenUnavailable("token endpoint answered a malformed body")
        return token, self._clock() + expires_in
