from typing import List, Dict
from uuid import UUID
from application.ports.output.rule_repository_port import RuleRepositoryPort
from domain.entities.rule import ScoringRule, RoutingRule

class InMemoryRuleRepository(RuleRepositoryPort):
    def __init__(self) -> None:
        self.scoring_rules: Dict[UUID, List[ScoringRule]] = {}
        self.routing_rules: Dict[UUID, List[RoutingRule]] = {}

    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        return self.scoring_rules.get(tenant_id, [])

    def get_routing_rules_by_tenant(self, tenant_id: UUID) -> List[RoutingRule]:
        return self.routing_rules.get(tenant_id, [])

    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        if tenant_id not in self.scoring_rules:
            self.scoring_rules[tenant_id] = []
        self.scoring_rules[tenant_id].append(rule)
        return rule

    def save_routing_rule(self, tenant_id: UUID, rule: RoutingRule) -> RoutingRule:
        if tenant_id not in self.routing_rules:
            self.routing_rules[tenant_id] = []
        self.routing_rules[tenant_id].append(rule)
        return rule
