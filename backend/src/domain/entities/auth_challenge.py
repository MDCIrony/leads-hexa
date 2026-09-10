from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AuthChallenge:
    token_hash: str
    agent_id: UUID | None
    purpose: str
    attempts: int
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime

