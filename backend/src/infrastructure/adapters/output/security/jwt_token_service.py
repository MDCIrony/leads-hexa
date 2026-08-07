from datetime import datetime, timedelta, timezone

import jwt

from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from domain.exceptions import UnauthorizedException

_ALGORITHM = "HS256"


class JwtTokenService(TokenServicePort):
    """PyJWT-backed adapter.

    The secret is injected rather than read from the environment here, so the
    composition root stays the single place that reads configuration."""

    def __init__(self, secret: str, expires_minutes: int = 60) -> None:
        if not secret:
            raise ValueError("JWT signing secret must not be empty")
        self._secret = secret
        self._expires_minutes = expires_minutes

    def issue(self, claims: TokenClaims) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": claims.agent_id,
            "role": claims.role,
            "tenant_id": claims.tenant_id,
            "exp": now + timedelta(minutes=self._expires_minutes),
            "iat": now,
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def verify(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as error:
            # Collapsing every PyJWT failure into one domain exception keeps
            # the library out of the caller's error handling.
            raise UnauthorizedException("Invalid or expired token") from error
        return TokenClaims(
            agent_id=payload["sub"],
            role=payload["role"],
            tenant_id=payload["tenant_id"],
        )
