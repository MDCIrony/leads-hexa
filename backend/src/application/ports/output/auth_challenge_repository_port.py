import abc
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.entities.auth_challenge import AuthChallenge


class AuthChallengeRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, challenge: AuthChallenge) -> None: ...

    @abc.abstractmethod
    def resolve_active(self, token_hash: str, now: datetime) -> Optional[AuthChallenge]: ...

    @abc.abstractmethod
    def increment_attempts(self, token_hash: str, now: datetime) -> bool: ...

    @abc.abstractmethod
    def reserve_attempt(self, token_hash: str, purpose: str, now: datetime, maximum: int) -> bool: ...

    @abc.abstractmethod
    def consume(self, token_hash: str, now: datetime) -> bool: ...

    @abc.abstractmethod
    def consume_oauth(
        self, token_hash: str, provider: str, state_hash: str, now: datetime
    ) -> Optional[AuthChallenge]: ...

    @abc.abstractmethod
    def invalidate_active_for_agent(self, agent_id: UUID, purpose: str, now: datetime) -> Optional[AuthChallenge]: ...
