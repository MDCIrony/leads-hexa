import abc
from typing import List, Optional
from uuid import UUID

from domain.groups.sales_group import SalesGroup


class SalesGroupRepositoryPort(abc.ABC):
    """Persists the sales groups that assignment rules target."""

    @abc.abstractmethod
    def save(self, group: SalesGroup) -> SalesGroup:
        """Insert or update a group."""

    @abc.abstractmethod
    def get_by_id(self, group_id: UUID) -> Optional[SalesGroup]:
        """Return the group with this identifier, if it exists."""

    @abc.abstractmethod
    def list_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[SalesGroup]:
        """Return a page of this organization's groups."""

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID) -> int:
        """Return how many groups this organization has."""

    @abc.abstractmethod
    def delete(self, group_id: UUID) -> None:
        """Delete a group.

        Its agents are not deleted with it: the foreign key sets their
        group_id to NULL instead (see migration 003)."""
