from __future__ import annotations
import abc
from typing import Any

from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.agent_repository_port import AgentRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.tenant_repository_port import TenantRepositoryPort
from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from application.ports.output.intake_record_repository_port import IntakeRecordRepositoryPort

class UnitOfWorkPort(abc.ABC):
    leads: LeadRepositoryPort
    rules: RuleRepositoryPort
    agents: AgentRepositoryPort
    tenants: TenantRepositoryPort
    groups: SalesGroupRepositoryPort
    sources: LeadSourceRepositoryPort
    intake_records: IntakeRecordRepositoryPort

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
