from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.commands import (
    CreateDisqualificationRuleCommand,
    DisqualificationRulesPageResult,
    UpdateDisqualificationRuleCommand,
)
from application.dtos.queries import GetDisqualificationRulesQuery
from domain.entities.disqualification_rule import DisqualificationRule


class CreateDisqualificationRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateDisqualificationRuleCommand) -> DisqualificationRule:
        pass


class GetDisqualificationRulesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetDisqualificationRulesQuery) -> DisqualificationRulesPageResult:
        pass


class UpdateDisqualificationRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateDisqualificationRuleCommand) -> DisqualificationRule:
        pass


class DeleteDisqualificationRuleInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, rule_id: UUID) -> None:
        pass
