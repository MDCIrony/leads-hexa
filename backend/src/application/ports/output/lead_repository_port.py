from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from domain.entities.lead import Lead
from domain.value_objects.enums import LeadStatus

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
    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus] = None,
        assigned_agent_id: Optional[UUID] = None,
        group_id: Optional[UUID] = None,
        source_id: Optional[UUID] = None,
        search: Optional[str] = None,
        updated_since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Lead]:
        pass

    @abstractmethod
    def count_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus] = None,
        assigned_agent_id: Optional[UUID] = None,
        group_id: Optional[UUID] = None,
        source_id: Optional[UUID] = None,
        search: Optional[str] = None,
        updated_since: Optional[datetime] = None,
    ) -> int:
        pass

    @abstractmethod
    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        pass

    @abstractmethod
    def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        status: Optional[LeadStatus] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Lead]:
        pass

    @abstractmethod
    def count_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        status: Optional[LeadStatus] = None,
        search: Optional[str] = None,
    ) -> int:
        pass

    @abstractmethod
    def active_load_by_agent(self, tenant_id: UUID) -> Dict[UUID, int]:
        """Return how many active leads each agent of this organization holds."""

    @abstractmethod
    def count_by_status(
        self,
        tenant_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Return how many leads this organization has in each status."""

    @abstractmethod
    def active_load_by_agent_with_names(self, tenant_id: UUID) -> List[Tuple[UUID, str, int]]:
        """Return each agent's active-lead load together with their name."""
