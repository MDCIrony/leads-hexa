import abc
from typing import Optional
from uuid import UUID

from domain.members.member import Member


class MemberRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def get(self, agent_id: UUID) -> Optional[Member]: ...

    @abc.abstractmethod
    def save(self, member: Member) -> None: ...

    @abc.abstractmethod
    def active_manager_ids(self, tenant_id: UUID) -> list[UUID]: ...
