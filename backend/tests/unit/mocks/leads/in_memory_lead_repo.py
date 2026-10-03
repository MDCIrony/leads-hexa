from datetime import datetime
from typing import List, Optional, Dict, Tuple
from uuid import UUID
from application.dtos.admissions import AdmissionLookupItem
from application.ports.output.leads.lead_repository_port import LeadRepositoryPort
from domain.leads.lead import Lead
from domain.value_objects.enums import LeadStatus

class InMemoryLeadRepository(LeadRepositoryPort):
    def __init__(self) -> None:
        self.leads: Dict[UUID, Lead] = {}
        # Wired by InMemoryUnitOfWork after both repos exist: resolving
        # group_id needs each lead's assigned advisor, which this repo has no
        # other way to reach.
        self.advisor_repo = None

    def save(self, lead: Lead) -> Lead:
        self.leads[lead.id.value] = lead
        return lead

    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        return self.leads.get(lead_id)

    def get_by_intake_record(self, tenant_id: UUID, intake_record_id: UUID) -> Optional[Lead]:
        return next((lead for lead in self.leads.values()
                     if lead.tenant_id.value == tenant_id and lead.intake_record_id == intake_record_id), None)

    def list_by_intake_records(self, intake_record_ids: List[UUID]) -> List[AdmissionLookupItem]:
        return [AdmissionLookupItem(str(lead.intake_record_id), str(lead.tenant_id.value), str(lead.id))
                for lead in self.leads.values() if lead.intake_record_id in set(intake_record_ids)]

    def get_by_id_and_tenant(self, lead_id: UUID, tenant_id: UUID) -> Optional[Lead]:
        lead = self.leads.get(lead_id)
        if lead is None or lead.tenant_id.value != tenant_id:
            return None
        return lead

    def _matches(
        self,
        lead: Lead,
        tenant_id: UUID,
        status: Optional[LeadStatus],
        assigned_agent_id: Optional[UUID],
        group_id: Optional[UUID],
        source_id: Optional[UUID],
        search: Optional[str],
        updated_since=None,
    ) -> bool:
        if lead.tenant_id.value != tenant_id:
            return False
        if updated_since is not None and lead.updated_at < updated_since:
            return False
        if status is not None and lead.status != status:
            return False
        if assigned_agent_id is not None and (
            lead.assigned_agent_id is None or lead.assigned_agent_id.value != assigned_agent_id
        ):
            return False
        if group_id is not None:
            agent = None
            if lead.assigned_agent_id is not None and self.advisor_repo is not None:
                agent = self.advisor_repo.advisors.get(lead.assigned_agent_id.value)
            agent_group_id = agent.group_id.value if agent and agent.group_id else None
            if agent_group_id != group_id:
                return False
        if source_id is not None and lead.source_id.value != source_id:
            return False
        if search:
            haystack = " ".join(
                filter(None, [lead.first_name, lead.last_name, str(lead.email) if lead.email else None, lead.company])
            ).lower()
            if search.lower() not in haystack:
                return False
        return True

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus] = None,
        assigned_agent_id: Optional[UUID] = None,
        group_id: Optional[UUID] = None,
        source_id: Optional[UUID] = None,
        search: Optional[str] = None,
        updated_since=None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Lead]:
        items = [
            l for l in self.leads.values()
            if self._matches(l, tenant_id, status, assigned_agent_id, group_id, source_id, search, updated_since)
        ]
        # Same two orders as the SQL adapter: catching up pages by the field
        # it filters on, so a row touched between pages is not skipped.
        if updated_since is not None:
            items.sort(key=lambda l: (l.updated_at, l.id.value))
        else:
            items.sort(key=lambda l: (l.created_at, l.id.value), reverse=True)
        return items[offset:offset + limit]

    def count_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus] = None,
        assigned_agent_id: Optional[UUID] = None,
        group_id: Optional[UUID] = None,
        source_id: Optional[UUID] = None,
        search: Optional[str] = None,
        updated_since=None,
    ) -> int:
        return len([
            l for l in self.leads.values()
            if self._matches(l, tenant_id, status, assigned_agent_id, group_id, source_id, search, updated_since)
        ])

    def _assigned_to(self, lead: Lead, tenant_id: UUID, agent_id: UUID) -> bool:
        return (
            lead.tenant_id.value == tenant_id
            and lead.assigned_agent_id is not None
            and lead.assigned_agent_id.value == agent_id
        )

    def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        status: Optional[LeadStatus] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Lead]:
        items = [
            l for l in self.leads.values()
            if self._assigned_to(l, tenant_id, agent_id)
            and self._matches(l, tenant_id, status, None, None, None, search)
        ]
        items.sort(key=lambda l: (l.assigned_at is not None, l.assigned_at, l.id.value), reverse=True)
        return items[offset:offset + limit]

    def count_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        status: Optional[LeadStatus] = None,
        search: Optional[str] = None,
    ) -> int:
        return len([
            l for l in self.leads.values()
            if self._assigned_to(l, tenant_id, agent_id)
            and self._matches(l, tenant_id, status, None, None, None, search)
        ])

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

    def count_by_status(
        self,
        tenant_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, int]:
        result = {s.value: 0 for s in LeadStatus}
        for lead in self.leads.values():
            if lead.tenant_id.value != tenant_id:
                continue
            if date_from is not None and lead.created_at < date_from:
                continue
            if date_to is not None and lead.created_at > date_to:
                continue
            result[lead.status.value] += 1
        return result

    def active_load_by_agent_with_names(self, tenant_id: UUID) -> List[Tuple[UUID, str, int]]:
        loads = self.active_load_by_agent(tenant_id)
        named = [
            (agent_id, self.advisor_repo.advisors[agent_id].name, load)
            for agent_id, load in loads.items()
            if self.advisor_repo is not None and agent_id in self.advisor_repo.advisors
        ]
        named.sort(key=lambda entry: (-entry[2], entry[1]))
        return named
