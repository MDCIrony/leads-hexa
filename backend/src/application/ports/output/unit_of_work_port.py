from __future__ import annotations
import abc
from typing import Any

from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.agent_repository_port import AgentRepositoryPort

class UnitOfWorkPort(abc.ABC):
    leads: LeadRepositoryPort
    rules: RuleRepositoryPort
    agents: AgentRepositoryPort

    def __enter__(self) -> UnitOfWorkPort:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @abc.abstractmethod
    def commit(self) -> None:
        pass

    @abc.abstractmethod
    def rollback(self) -> None:
        pass
