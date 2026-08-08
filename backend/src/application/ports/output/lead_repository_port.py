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
    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        pass

    @abstractmethod
    def count_by_tenant(self, tenant_id: UUID) -> int:
        pass

    @abstractmethod
    def active_load_by_agent(self, tenant_id: UUID) -> Dict[UUID, int]:
        """Return how many active leads each agent of this organization holds."""
