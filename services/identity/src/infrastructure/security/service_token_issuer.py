import time
from uuid import uuid4

from chassis.auth import ISSUER, SERVICE_PTYPE, Ed25519Signer

from domain.exceptions import UnauthorizedException
from infrastructure.security.service_clients import ServiceClients


class ServiceTokenIssuer:
    """Client credentials for calls with no user behind them: `sub` is the caller,
    `aud` the service it may call. Same signer and kid as the internal token, so
    every service verifies both against the one JWKS."""

    TTL_SECONDS = 300

    def __init__(self, signer: Ed25519Signer, clients: ServiceClients) -> None:
        self._signer = signer
        self._clients = clients

    def issue(self, client_id: str, client_secret: str, audience: str) -> str:
        """Raises UnauthorizedException, one message for every failure: saying which
        check failed would tell a caller which client ids exist."""
        if not self._clients.authenticate(client_id, client_secret, audience):
            raise UnauthorizedException("Invalid service credentials")
        now = int(time.time())
        return self._signer.sign({
            "iss": ISSUER, "sub": client_id, "aud": audience, "ptype": SERVICE_PTYPE,
            "iat": now, "exp": now + self.TTL_SECONDS, "jti": str(uuid4()),
        })
