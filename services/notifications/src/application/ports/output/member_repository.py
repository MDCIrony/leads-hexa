from abc import ABC, abstractmethod
from uuid import UUID

from domain.members.member import Member


class MemberRepositoryPort(ABC):
    @abstractmethod
    def get(self, agent_id: UUID) -> Member | None: ...

    @abstractmethod
    def save(self, member: Member) -> None: ...

    @abstractmethod
    def active_manager_ids(self, tenant_id: UUID) -> list[UUID]: ...
