import abc
from typing import List, Optional
from uuid import UUID

from domain.entities.tenant import Tenant


class TenantRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, tenant: Tenant) -> Tenant:
        """Insert or update an organization."""

    @abc.abstractmethod
    def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """Return the organization with this identifier, if it exists."""

    @abc.abstractmethod
    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Return the organization with this slug, if it exists."""

    @abc.abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        """Return a page of organizations, ordered deterministically."""

    @abc.abstractmethod
    def count_all(self) -> int:
        """Return how many organizations exist."""

    @abc.abstractmethod
    def count_active_agents(self, tenant_id: UUID) -> int:
        """Return how many active users this organization has.

        An aggregate, deliberately: the platform plane sees activity without
        seeing identities."""
