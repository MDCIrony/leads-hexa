from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from application.dtos.commands import (
    CreateAssignmentRuleCommand,
    CreateScoringRuleCommand,
    UpdateAssignmentRuleCommand,
)
from application.dtos.queries import GetAssignmentRulesQuery, GetRulesQuery
from domain.entities.rule import AssignmentRule, ScoringRule


class GetScoringRulesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetRulesQuery) -> List[ScoringRule]:
        pass


class CreateScoringRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateScoringRuleCommand) -> ScoringRule:
        pass


class CreateAssignmentRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateAssignmentRuleCommand) -> AssignmentRule:
        pass


class GetAssignmentRulesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetAssignmentRulesQuery) -> List[AssignmentRule]:
        pass


class UpdateAssignmentRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateAssignmentRuleCommand) -> AssignmentRule:
        pass


class DeleteAssignmentRuleInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, rule_id: UUID) -> None:
        pass
