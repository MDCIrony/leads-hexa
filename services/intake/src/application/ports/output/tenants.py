from abc import ABC, abstractmethod
from uuid import UUID


class ProvisionedTenantRepositoryPort(ABC):
    @abstractmethod
    def mark(self, tenant_id: UUID) -> bool:
        """Record that `tenant_id` got its default sources, inside the caller's transaction.

        True if this call inserted the row, False if the tenant was already provisioned."""
