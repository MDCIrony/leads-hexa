from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.agent_repository_port import AgentRepositoryPort
from application.ports.output.intake_record_repository_port import IntakeRecordRepositoryPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.tenant_repository_port import TenantRepositoryPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_lead_source_repo import InMemoryLeadSourceRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_tenant_repo import InMemoryTenantRepository


class InMemoryIntakeRecordRepository(IntakeRecordRepositoryPort):
    """Kept inline (unlike the other mocks) because no other test needs it yet."""

    def __init__(self) -> None:
        self._records: Dict[UUID, IntakeRecord] = {}

    def save(self, record: IntakeRecord) -> IntakeRecord:
        self._records[record.id.value] = record
        return record

    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        record = self._records.get(record_id)
        return record if record and record.tenant_id.value == tenant_id else None

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeRecord]:
        matches = [
            r
            for r in self._records.values()
            if r.tenant_id.value == tenant_id and (status is None or r.status == status)
        ]
        matches.sort(key=lambda r: r.received_at)
        return matches[offset : offset + limit]

    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None) -> int:
        return sum(
            1
            for r in self._records.values()
            if r.tenant_id.value == tenant_id and (status is None or r.status == status)
        )


class InMemoryUnitOfWork(UnitOfWorkPort):
    def __init__(
        self,
        lead_repo: Optional[LeadRepositoryPort] = None,
        rule_repo: Optional[RuleRepositoryPort] = None,
        agent_repo: Optional[AgentRepositoryPort] = None,
        leads: Optional[LeadRepositoryPort] = None,
        rules: Optional[RuleRepositoryPort] = None,
        agents: Optional[AgentRepositoryPort] = None,
        tenants: Optional[TenantRepositoryPort] = None,
        groups: Optional[SalesGroupRepositoryPort] = None,
        sources: Optional[LeadSourceRepositoryPort] = None,
        intake_records: Optional[IntakeRecordRepositoryPort] = None,
    ) -> None:
        # Defaulting to a fresh in-memory repo (instead of None) is what lets
        # a test that only cares about leads and agents write
        # InMemoryUnitOfWork() and go, instead of wiring up every repo by hand.
        self.leads = leads if leads is not None else (lead_repo or InMemoryLeadRepository())
        self.rules = rules if rules is not None else (rule_repo or InMemoryRuleRepository())
        self.agents = agents if agents is not None else (agent_repo or InMemoryAgentRepository())
        self.tenants = tenants or InMemoryTenantRepository()
        self.groups = groups or InMemorySalesGroupRepository()
        self.sources = sources or InMemoryLeadSourceRepository()
        self.intake_records = intake_records or InMemoryIntakeRecordRepository()

    def __enter__(self) -> 'InMemoryUnitOfWork':
        return self

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
