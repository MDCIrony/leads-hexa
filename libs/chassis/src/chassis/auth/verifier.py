import jwt

from chassis.auth.claims import PRINCIPAL_TYPES, Claims, TokenError
from chassis.auth.jwks import JwksCache
from chassis.auth.signing import ALGORITHM

_REQUIRED_CLAIMS = ["iss", "aud", "sub", "iat", "exp", "jti"]


class TokenVerifier:
    def __init__(self, jwks: JwksCache, *, issuer: str, audience: str, leeway: int = 5) -> None:
        self._jwks = jwks
        self._issuer = issuer
        self._audience = audience
        self._leeway = leeway

    def verify(self, token: str) -> Claims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise TokenError("malformed token") from error
        kid = header.get("kid")
        # Checked before any key is chosen: the algorithm is ours to fix,
        # never the token's to declare.
        if header.get("alg") != ALGORITHM or not isinstance(kid, str):
            raise TokenError("unexpected token header")
        key = self._jwks.key(kid)
        try:
            payload = jwt.decode(
                token, key, algorithms=[ALGORITHM], audience=self._audience,
                issuer=self._issuer, leeway=self._leeway,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as error:
            raise TokenError("invalid token") from error
        role, ptype, tid = payload.get("role"), payload.get("ptype"), payload.get("tid")
        if not isinstance(role, str) or not isinstance(ptype, str) or not (
            tid is None or isinstance(tid, str)
        ):
            raise TokenError("invalid token claims")
        # Identity always issues a coherent pair; anything else is not ours.
        if ptype not in PRINCIPAL_TYPES or (role == "INTEGRATION") != (ptype == "integration"):
            raise TokenError("invalid token claims")
        return Claims(
            sub=str(payload["sub"]), tid=tid, role=role, ptype=ptype,
            aud=str(payload["aud"]), jti=str(payload["jti"]), exp=int(payload["exp"]),
        )
