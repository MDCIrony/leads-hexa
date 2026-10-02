"""The services allowed to ask for a service token, read from SERVICE_CLIENTS.

Format: `client_id:audience[|audience]:sha256hex[,…]`. Only the SHA-256 of each
secret is configured: the secret is generated with high entropy, so a fast hash
is enough, and identity never holds the secret itself."""
import hashlib
import hmac
import re
from dataclasses import dataclass, field

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[A-Za-z0-9._-]+")
_FORMAT = "client_id:audience[|audience]:sha256hex"
# Compared against when the client is unknown, so that path costs the same as a
# wrong secret. No input hashes to it in practice.
_NO_SECRET = bytes(32)


@dataclass(frozen=True)
class ServiceClient:
    client_id: str
    audiences: frozenset[str]
    # Out of repr: settings get logged, and a digest is not for logs either.
    secret_sha256: bytes = field(repr=False)


def parse_service_clients(spec: str) -> tuple[ServiceClient, ...]:
    """Raises ValueError naming the entry by position: an entry that fails to split
    could put the hash where the client id should be, so neither is echoed."""
    clients: list[ServiceClient] = []
    for position, entry in enumerate((part.strip() for part in spec.split(",")), start=1):
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3:
            raise ValueError(f"SERVICE_CLIENTS entry #{position} must look like {_FORMAT}")
        client_id, audiences, digest = (part.strip() for part in parts)
        names = [name.strip() for name in audiences.split("|")]
        if not _NAME.fullmatch(client_id) or not all(_NAME.fullmatch(name) for name in names):
            raise ValueError(f"SERVICE_CLIENTS entry #{position} has an empty or invalid name")
        if not _SHA256_HEX.fullmatch(digest.lower()):
            raise ValueError(f"SERVICE_CLIENTS entry #{position} needs a 64-character SHA-256 hex digest")
        clients.append(ServiceClient(client_id, frozenset(names), bytes.fromhex(digest)))
    if not clients:
        raise ValueError("SERVICE_CLIENTS is required and has no default")
    if len({client.client_id for client in clients}) != len(clients):
        raise ValueError("SERVICE_CLIENTS has a repeated client_id")
    return tuple(clients)


class ServiceClients:
    def __init__(self, clients: tuple[ServiceClient, ...]) -> None:
        self._by_id = {client.client_id: client for client in clients}

    def authenticate(self, client_id: str, client_secret: str, audience: str) -> bool:
        """True only for a known client, its exact secret and one of its audiences.

        Every check runs whatever the earlier ones said: an early return would let
        the response time tell an unknown client from a wrong secret."""
        client = self._by_id.get(client_id)
        presented = hashlib.sha256(client_secret.encode()).digest()
        secret_matches = hmac.compare_digest(presented, client.secret_sha256 if client else _NO_SECRET)
        audience_allowed = client is not None and audience in client.audiences
        return client is not None and secret_matches and audience_allowed
