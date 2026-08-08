from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from domain.entities.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind


class InMemoryLeadSourceRepository(LeadSourceRepositoryPort):
    def __init__(self) -> None:
        self.sources: Dict[UUID, LeadSource] = {}

    def save(self, source: LeadSource) -> LeadSource:
        self.sources[source.id.value] = source
        return source

    def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> Optional[LeadSource]:
        source = self.sources.get(source_id)
        return source if source and source.tenant_id.value == tenant_id else None

    def get_by_kind(self, tenant_id: UUID, kind: LeadSourceKind) -> Optional[LeadSource]:
        for source in self.sources.values():
            if source.tenant_id.value == tenant_id and source.kind == kind:
                return source
        return None

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[LeadSource]:
        items = [s for s in self.sources.values() if s.tenant_id.value == tenant_id]
        items.sort(key=lambda s: (s.name, str(s.id)))
        return items[offset : offset + limit]

    def delete(self, source_id: UUID, tenant_id: UUID) -> bool:
        source = self.sources.get(source_id)
        if source and source.tenant_id.value == tenant_id:
            del self.sources[source_id]
            return True
        return False
