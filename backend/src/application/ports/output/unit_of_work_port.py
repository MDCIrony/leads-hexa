from __future__ import annotations
import abc
from typing import Any

from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.disqualification_rule_repository_port import DisqualificationRuleRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from application.ports.output.processed_event_repository_port import ProcessedEventRepositoryPort
from application.ports.output.advisors.advisor_repository_port import AdvisorRepositoryPort

class UnitOfWorkPort(abc.ABC):
    leads: LeadRepositoryPort
    rules: RuleRepositoryPort
    disqualification_rules: DisqualificationRuleRepositoryPort
    groups: SalesGroupRepositoryPort
    outbox: OutboxRepositoryPort
    processed_events: ProcessedEventRepositoryPort
    advisors: AdvisorRepositoryPort

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
