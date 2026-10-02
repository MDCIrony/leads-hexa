from dataclasses import dataclass
from typing import Optional


ISSUER = "identity"
AUDIENCE = "lead-router"
PRINCIPAL_TYPES = ("human", "integration")


class TokenError(Exception):
    """The token cannot be trusted. Callers map it to 401 without detail."""


class KeysUnavailable(TokenError):
    """The signing keys could not be fetched or parsed. Not the caller's
    fault, so callers map it to 503 instead of 401."""


@dataclass(frozen=True)
class Claims:
    sub: str
    tid: Optional[str]
    role: str
    ptype: str
    aud: str
    jti: str
    exp: int
