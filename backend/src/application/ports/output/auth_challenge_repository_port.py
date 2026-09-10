import abc
from datetime import datetime
from typing import Optional

from domain.entities.auth_challenge import AuthChallenge


class AuthChallengeRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, challenge: AuthChallenge) -> None: ...

    @abc.abstractmethod
    def resolve_active(self, token_hash: str, now: datetime) -> Optional[AuthChallenge]: ...

    @abc.abstractmethod
    def increment_attempts(self, token_hash: str, now: datetime) -> bool: ...

    @abc.abstractmethod
    def consume(self, token_hash: str, now: datetime) -> bool: ...
