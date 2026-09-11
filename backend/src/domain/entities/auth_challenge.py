from dataclasses import dataclass
from datetime import datetime
from hmac import compare_digest
from urllib.parse import urlsplit
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
    provider: str | None = None
    state_hash: str | None = None
    pkce_verifier: str | None = None
    return_path: str | None = None

    def __post_init__(self) -> None:
        if not self.purpose or not self.purpose.strip():
            raise InvalidAuthChallengeException("Challenge purpose must not be empty")
        if self.attempts < 0:
            raise InvalidAuthChallengeException("Challenge attempts must not be negative")
        oauth_values = (self.provider, self.state_hash, self.pkce_verifier, self.return_path)
        if self.purpose == "OAUTH_LOGIN":
            if (
                self.provider not in {"GOOGLE", "GITHUB"}
                or any(not value or not value.strip() for value in oauth_values)
                or not self._internal_return_path(self.return_path)
            ):
                raise InvalidAuthChallengeException("OAuth challenge is incomplete")
        elif any(value is not None for value in oauth_values):
            raise InvalidAuthChallengeException("Only OAuth challenges may carry OAuth data")

    @staticmethod
    def _internal_return_path(value: str | None) -> bool:
        if not value or any(ord(character) < 32 or ord(character) == 127 for character in value):
            return False
        try:
            parts = urlsplit(value)
        except ValueError:
            return False
        return (
            parts.path.startswith("/")
            and not value.startswith("//")
            and not parts.scheme
            and not parts.netloc
            and not parts.query
            and not parts.fragment
            and "\\" not in value
        )

    def matches_oauth(self, provider: str, state_hash: str) -> bool:
        return (
            self.purpose == "OAUTH_LOGIN"
            and self.provider is not None
            and self.state_hash is not None
            and compare_digest(self.provider, provider)
            and compare_digest(self.state_hash, state_hash)
        )
