from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from application.dtos.rules import (
    CreateAssignmentRuleCommand,
    CreateScoringRuleCommand,
    GetAssignmentRulesQuery,
    GetRulesQuery,
    ScoringRulesPageResult,
    UpdateAssignmentRuleCommand,
    UpdateScoringRuleCommand,
)
from domain.rules.assignment_rule import AssignmentRule
from domain.rules.scoring_rule import ScoringRule


class GetScoringRulesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetRulesQuery) -> ScoringRulesPageResult:
        pass


class CreateScoringRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateScoringRuleCommand) -> ScoringRule:
        pass


class UpdateScoringRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateScoringRuleCommand) -> ScoringRule:
        pass


class DeleteScoringRuleInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, rule_id: UUID) -> None:
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
