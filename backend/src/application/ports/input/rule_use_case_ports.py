from abc import ABC, abstractmethod
from typing import List
from application.dtos.queries import GetRulesQuery
from application.dtos.commands import CreateScoringRuleCommand, CreateRoutingRuleCommand
from domain.entities.rule import ScoringRule, RoutingRule

class GetScoringRulesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetRulesQuery) -> List[ScoringRule]:
        pass

class CreateScoringRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateScoringRuleCommand) -> ScoringRule:
        pass

class GetRoutingRulesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetRulesQuery) -> List[RoutingRule]:
        pass

class CreateRoutingRuleInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateRoutingRuleCommand) -> RoutingRule:
        pass
