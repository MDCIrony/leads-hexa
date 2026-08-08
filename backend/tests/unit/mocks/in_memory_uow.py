from typing import Optional

from application.ports.output.agent_repository_port import AgentRepositoryPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.tenant_repository_port import TenantRepositoryPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort

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
    ) -> None:
        self.leads = leads if leads is not None else lead_repo
        self.rules = rules if rules is not None else rule_repo
        self.agents = agents if agents is not None else agent_repo
        self.tenants = tenants
        self.groups = groups

    def __enter__(self) -> 'InMemoryUnitOfWork':
        return self

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
