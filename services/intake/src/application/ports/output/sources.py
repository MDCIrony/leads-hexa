from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind


class LeadSourceRepositoryPort(ABC):
    @abstractmethod
    def save(self, source: LeadSource) -> LeadSource: ...

    @abstractmethod
    def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> Optional[LeadSource]: ...

    @abstractmethod
    def get_by_kind(self, tenant_id: UUID, kind: LeadSourceKind) -> Optional[LeadSource]: ...

    @abstractmethod
    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[LeadSource]: ...

    @abstractmethod
    def delete(self, source_id: UUID, tenant_id: UUID) -> bool: ...
