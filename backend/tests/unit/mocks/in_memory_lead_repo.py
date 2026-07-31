from typing import List, Optional, Dict
from uuid import UUID
from application.ports.output.lead_repository_port import LeadRepositoryPort
from domain.entities.lead import Lead

class InMemoryLeadRepository(LeadRepositoryPort):
    def __init__(self) -> None:
        self.leads: Dict[UUID, Lead] = {}

    def save(self, lead: Lead) -> Lead:
        self.leads[lead.id.value] = lead
        return lead

    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        return self.leads.get(lead_id)

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        items = [l for l in self.leads.values() if l.tenant_id.value == tenant_id]
        return items[offset:offset + limit]
