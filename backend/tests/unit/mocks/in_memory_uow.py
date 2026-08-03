from typing import Any
from application.ports.output.unit_of_work_port import UnitOfWorkPort

class InMemoryUnitOfWork(UnitOfWorkPort):
    def __init__(self, lead_repo, rule_repo, agent_repo):
        self.leads = lead_repo
        self.rules = rule_repo
        self.agents = agent_repo

    def __enter__(self) -> 'InMemoryUnitOfWork':
        return self
        
    def commit(self) -> None:
        pass
        
    def rollback(self) -> None:
        pass
