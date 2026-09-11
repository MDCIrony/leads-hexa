import abc
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.entities.auth_session import AuthSession


class AuthSessionRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, session: AuthSession) -> None: ...

    @abc.abstractmethod
    def get_active(self, token_hash: str, now: datetime) -> Optional[AuthSession]: ...

    @abc.abstractmethod
    def revoke(self, token_hash: str, now: datetime) -> None: ...

    @abc.abstractmethod
    def revoke_for_agent_except(self, agent_id: UUID, token_hash: str, now: datetime) -> None: ...
