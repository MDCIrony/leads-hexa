from dataclasses import dataclass
from typing import Optional


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
