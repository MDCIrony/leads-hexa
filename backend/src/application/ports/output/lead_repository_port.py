from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from uuid import UUID
from domain.entities.lead import Lead

class LeadRepositoryPort(ABC):
    @abstractmethod
    def save(self, lead: Lead) -> Lead:
        pass

    @abstractmethod
    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        pass

    @abstractmethod
    def get_by_id_and_tenant(self, lead_id: UUID, tenant_id: UUID) -> Optional[Lead]:
        """Reading across organizations must be impossible, not merely forbidden."""

    @abstractmethod
    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        pass

    @abstractmethod
    def count_by_tenant(self, tenant_id: UUID) -> int:
        pass

    @abstractmethod
    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        pass

    @abstractmethod
    def list_by_agent(
        self, tenant_id: UUID, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Lead]:
        pass

    @abstractmethod
    def count_by_agent(self, tenant_id: UUID, agent_id: UUID) -> int:
        pass

    @abstractmethod
    def active_load_by_agent(self, tenant_id: UUID) -> Dict[UUID, int]:
        """Return how many active leads each agent of this organization holds."""
