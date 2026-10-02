from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from domain.advisors.advisor import Advisor


class AdvisorRepositoryPort(ABC):
    @abstractmethod
    def get(self, agent_id: UUID, tenant_id: UUID) -> Optional[Advisor]:
        """None for an advisor of another organization: a 403 would confirm it exists."""

    @abstractmethod
    def list_available(self, tenant_id: UUID, group_id: Optional[UUID] = None) -> List[Advisor]:
        """Active advisors a lead can be routed to, ordered by name then id."""

    @abstractmethod
    def list(
        self,
        tenant_id: UUID,
        group_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Advisor]: ...

    @abstractmethod
    def count_by_group(self, tenant_id: UUID, group_id: UUID) -> int:
        """Active advisors in the group, as the groups listing shows them."""

    @abstractmethod
    def upsert_identity(self, advisor: Advisor) -> None:
        """Writes the identity columns only if `advisor` is newer than the stored row.

        Never touches `group_id`: that column is lead-core's, not identity's."""

    @abstractmethod
    def set_group(self, agent_id: UUID, tenant_id: UUID, group_id: Optional[UUID]) -> bool:
        """True if the advisor exists in this organization and was updated."""
