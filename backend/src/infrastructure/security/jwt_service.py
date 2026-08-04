import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

_ALGORITHM = "HS256"


def _get_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET environment variable is not set")
    return secret


def create_access_token(
    agent_id: str,
    role: str,
    tenant_id: Optional[str],
    expires_minutes: int = 60,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": agent_id,
        "role": role,
        "tenant_id": tenant_id,
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
    }
    return jwt.encode(payload, _get_secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _get_secret(), algorithms=[_ALGORITHM])
