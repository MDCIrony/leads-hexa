from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from domain.sessions.auth_challenge import AuthChallenge
from domain.sessions.auth_session import AuthSession


class AuthSessionRepositoryPort(ABC):
    @abstractmethod
    def save(self, session: AuthSession) -> None: ...

    @abstractmethod
    def get_active(self, token_hash: str, now: datetime) -> AuthSession | None:
        """Neither revoked nor expired at now."""

    @abstractmethod
    def revoke(self, token_hash: str, now: datetime) -> None: ...

    @abstractmethod
    def revoke_for_agent_except(self, agent_id: UUID, token_hash: str, now: datetime) -> None: ...


class AuthChallengeRepositoryPort(ABC):
    @abstractmethod
    def save(self, challenge: AuthChallenge) -> None: ...

    @abstractmethod
    def resolve_active(self, token_hash: str, now: datetime) -> AuthChallenge | None:
        """Neither consumed nor expired at now."""

    @abstractmethod
    def increment_attempts(self, token_hash: str, now: datetime) -> bool: ...

    @abstractmethod
    def reserve_attempt(self, token_hash: str, purpose: str, now: datetime, maximum: int) -> bool:
        """Atomically count one attempt on a live challenge of this purpose still under maximum."""

    @abstractmethod
    def consume(self, token_hash: str, now: datetime) -> bool:
        """True only for the one caller that consumed a live challenge."""

    @abstractmethod
    def consume_oauth(
        self, token_hash: str, provider: str, state_hash: str, now: datetime
    ) -> AuthChallenge | None:
        """Consume a live OAuth challenge bound to this provider and state, at most once."""

    @abstractmethod
    def invalidate_active_for_agent(
        self, agent_id: UUID, purpose: str, now: datetime
    ) -> AuthChallenge | None:
        """Consume the agent's live challenges of this purpose; returns the one with most attempts."""
