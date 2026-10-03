from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.rules import (
    CreateDisqualificationRuleCommand,
    DisqualificationRulesPageResult,
    GetDisqualificationRulesQuery,
    UpdateDisqualificationRuleCommand,
)
from domain.rules.disqualification_rule import DisqualificationRule


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
