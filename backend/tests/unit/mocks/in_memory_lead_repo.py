from typing import List, Optional, Dict
from uuid import UUID
from application.ports.output.lead_repository_port import LeadRepositoryPort
from domain.entities.lead import Lead
from domain.value_objects.enums import LeadStatus

class InMemoryLeadRepository(LeadRepositoryPort):
    def __init__(self) -> None:
        self.leads: Dict[UUID, Lead] = {}

    def save(self, lead: Lead) -> Lead:
        self.leads[lead.id.value] = lead
        return lead

    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        return self.leads.get(lead_id)

    def get_by_id_and_tenant(self, lead_id: UUID, tenant_id: UUID) -> Optional[Lead]:
        lead = self.leads.get(lead_id)
        if lead is None or lead.tenant_id.value != tenant_id:
            return None
        return lead

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        items = [l for l in self.leads.values() if l.tenant_id.value == tenant_id]
        return items[offset:offset + limit]

    def count_by_tenant(self, tenant_id: UUID) -> int:
        return len([l for l in self.leads.values() if l.tenant_id.value == tenant_id])

    def _assigned_to(self, lead: Lead, tenant_id: UUID, agent_id: UUID) -> bool:
        return (
            lead.tenant_id.value == tenant_id
            and lead.assigned_agent_id is not None
            and lead.assigned_agent_id.value == agent_id
        )

    def list_by_agent(
        self, tenant_id: UUID, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Lead]:
        items = [l for l in self.leads.values() if self._assigned_to(l, tenant_id, agent_id)]
        return items[offset:offset + limit]

    def count_by_agent(self, tenant_id: UUID, agent_id: UUID) -> int:
        return len([l for l in self.leads.values() if self._assigned_to(l, tenant_id, agent_id)])

    def active_load_by_agent(self, tenant_id: UUID) -> Dict[UUID, int]:
        loads: Dict[UUID, int] = {}
        for lead in self.leads.values():
            if (
                lead.tenant_id.value == tenant_id
                and lead.status == LeadStatus.ASSIGNED
                and lead.assigned_agent_id is not None
            ):
                agent_id = lead.assigned_agent_id.value
                loads[agent_id] = loads.get(agent_id, 0) + 1
        return loads
