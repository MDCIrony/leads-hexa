from typing import Any, Optional
from application.ports.output.unit_of_work_port import UnitOfWorkPort

class InMemoryUnitOfWork(UnitOfWorkPort):
    def __init__(self, lead_repo=None, rule_repo=None, agent_repo=None, leads=None, rules=None, agents=None, tenants=None):
        self.leads = leads if leads is not None else lead_repo
        self.rules = rules if rules is not None else rule_repo
        self.agents = agents if agents is not None else agent_repo
        self.tenants = tenants

    def __enter__(self) -> 'InMemoryUnitOfWork':
        return self
        
    def commit(self) -> None:
        pass
        
    def rollback(self) -> None:
        pass
