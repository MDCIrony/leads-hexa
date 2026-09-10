from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.exceptions import InvalidAuthChallengeException


@dataclass(frozen=True)
class AuthChallenge:
    token_hash: str
    agent_id: UUID | None
    purpose: str
    attempts: int
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.purpose or not self.purpose.strip():
            raise InvalidAuthChallengeException("Challenge purpose must not be empty")
        if self.attempts < 0:
            raise InvalidAuthChallengeException("Challenge attempts must not be negative")

