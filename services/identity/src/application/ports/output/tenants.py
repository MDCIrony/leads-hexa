from abc import ABC, abstractmethod
from uuid import UUID

from domain.tenants.tenant import Tenant


class TenantRepositoryPort(ABC):
    @abstractmethod
    def save(self, tenant: Tenant) -> Tenant:
        """Insert or update; returns the tenant with the version the database assigned."""

    @abstractmethod
    def get_by_id(self, tenant_id: UUID) -> Tenant | None: ...

    @abstractmethod
    def get_by_slug(self, slug: str) -> Tenant | None: ...

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> list[Tenant]:
        """A page of organizations, newest first, id as tiebreaker."""

    @abstractmethod
    def count_all(self) -> int: ...

    @abstractmethod
    def count_active_agents(self, tenant_id: UUID) -> int:
        """An aggregate on purpose: the platform plane sees activity, not identities."""
