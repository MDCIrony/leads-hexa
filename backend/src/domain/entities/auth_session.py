from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AuthSession:
    token_hash: str
    agent_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

