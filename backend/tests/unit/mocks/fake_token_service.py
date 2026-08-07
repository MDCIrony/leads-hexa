import json

from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from domain.exceptions import UnauthorizedException


class FakeTokenService(TokenServicePort):
    """Reversible stand-in with no signing. Lets unit tests assert on the
    claims a use case issued without depending on a JWT secret."""

    def issue(self, claims: TokenClaims) -> str:
        return json.dumps(
            {
                "agent_id": claims.agent_id,
                "role": claims.role,
                "tenant_id": claims.tenant_id,
            }
        )

    def verify(self, token: str) -> TokenClaims:
        try:
            payload = json.loads(token)
        except (ValueError, TypeError):
            raise UnauthorizedException("Invalid token")
        return TokenClaims(
            agent_id=payload["agent_id"],
            role=payload["role"],
            tenant_id=payload["tenant_id"],
        )
