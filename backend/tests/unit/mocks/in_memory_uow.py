from typing import Optional

from application.ports.output.agent_repository_port import AgentRepositoryPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.tenant_repository_port import TenantRepositoryPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_lead_source_repo import InMemoryLeadSourceRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_tenant_repo import InMemoryTenantRepository

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

    def __enter__(self) -> 'InMemoryUnitOfWork':
        return self

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
