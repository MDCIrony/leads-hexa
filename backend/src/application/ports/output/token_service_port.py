import abc
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TokenClaims:
    """Identity carried by an access token.

    Deliberately primitive: this crosses the boundary to an adapter that knows
    nothing about the domain's value objects."""

    agent_id: str
    role: str
    tenant_id: Optional[str]


class TokenServicePort(abc.ABC):
    """Issues and verifies access tokens. The token format is an
    infrastructure concern."""

    @abc.abstractmethod
    def issue(self, claims: TokenClaims) -> str:
        """Return a signed token carrying the given claims."""

    @abc.abstractmethod
    def verify(self, token: str) -> TokenClaims:
        """Return the claims of a valid token.

        Raises UnauthorizedException when the token is malformed, tampered
        with, or expired."""
