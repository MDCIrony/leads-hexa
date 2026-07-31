from abc import ABC, abstractmethod
from typing import List
from uuid import UUID
from domain.entities.rule import ScoringRule, RoutingRule

class RuleRepositoryPort(ABC):
    @abstractmethod
    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        pass

    @abstractmethod
    def get_routing_rules_by_tenant(self, tenant_id: UUID) -> List[RoutingRule]:
        pass

    @abstractmethod
    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        pass

    @abstractmethod
    def save_routing_rule(self, tenant_id: UUID, rule: RoutingRule) -> RoutingRule:
        pass
