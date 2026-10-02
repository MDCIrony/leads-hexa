from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.social.social_identity import SocialIdentity


class SocialIdentityRepositoryPort(ABC):
    @abstractmethod
    def get_by_provider_subject(self, provider: str, provider_subject: str) -> SocialIdentity | None: ...

    @abstractmethod
    def list_by_agent(self, agent_id: UUID) -> list[SocialIdentity]:
        """Ordered by provider."""

    @abstractmethod
    def save(self, identity: SocialIdentity) -> bool:
        """False when the subject, or this agent's link to this provider, already exists."""

    @abstractmethod
    def touch_last_login(self, identity_id: UUID, now: datetime) -> bool: ...


@dataclass(frozen=True)
class OAuthIdentity:
    provider_subject: str
    email: str | None
    email_verified: bool
    name: str | None


class OAuthIdentityProviderError(Exception):
    """An external OAuth response cannot establish an application identity."""


class OAuthIdentityProviderPort(ABC):
    @abstractmethod
    def exchange(self, code: str, pkce_verifier: str) -> OAuthIdentity:
        """Raises OAuthIdentityProviderError on any provider failure."""
