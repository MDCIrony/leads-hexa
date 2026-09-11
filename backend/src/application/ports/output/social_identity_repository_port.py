import abc
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.entities.social_identity import SocialIdentity


class SocialIdentityRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def get_by_provider_subject(self, provider: str, provider_subject: str) -> Optional[SocialIdentity]: ...

    @abc.abstractmethod
    def save(self, identity: SocialIdentity) -> bool: ...

    @abc.abstractmethod
    def touch_last_login(self, identity_id: UUID, now: datetime) -> bool: ...
