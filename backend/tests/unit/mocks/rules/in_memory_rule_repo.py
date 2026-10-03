from typing import List, Dict, Optional
from uuid import UUID
from application.ports.output.rules.rule_repository_port import RuleRepositoryPort
from domain.rules.assignment_rule import AssignmentRule
from domain.rules.scoring_rule import ScoringRule

class InMemoryRuleRepository(RuleRepositoryPort):
    def __init__(self) -> None:
        self.scoring_rules: Dict[UUID, List[ScoringRule]] = {}
        self.assignment_rules: Dict[UUID, AssignmentRule] = {}

    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        return self.scoring_rules.get(tenant_id, [])

    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        # Mirrors the SQL adapter's ON CONFLICT (id) DO UPDATE: appending made
        # a re-saved rule apply twice, which no real repository would do.
        bucket = self.scoring_rules.setdefault(tenant_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == rule.id:
                bucket[index] = rule
                return rule
        bucket.append(rule)
        return rule

    def get_scoring_rule_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[ScoringRule]:
        return next((r for r in self.scoring_rules.get(tenant_id, []) if r.id == rule_id), None)

    def list_scoring_rules_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[ScoringRule]:
        # Mirrors RawSqlRuleRepository's ORDER BY priority DESC, id.
        items = sorted(self.scoring_rules.get(tenant_id, []), key=lambda r: (-r.priority, str(r.id)))
        return items[offset : offset + limit]

    def count_scoring_rules_by_tenant(self, tenant_id: UUID) -> int:
        return len(self.scoring_rules.get(tenant_id, []))

    def delete_scoring_rule(self, rule_id: UUID, tenant_id: UUID) -> bool:
        bucket = self.scoring_rules.get(tenant_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == rule_id:
                del bucket[index]
                return True
        return False

    def lock_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        # Nothing to lock against in a single-threaded double; the locking is
        # what the SQL adapter adds, and what its own test exercises.
        return self.get_assignment_rules_by_tenant(tenant_id)

    def get_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        rules = [r for r in self.assignment_rules.values() if r.tenant_id == tenant_id]
        # Mirrors RawSqlRuleRepository's ORDER BY priority DESC, id.
        return sorted(rules, key=lambda r: (-r.priority, str(r.id)))

    def save_assignment_rule(self, tenant_id: UUID, rule: AssignmentRule) -> AssignmentRule:
        self.assignment_rules[rule.id] = rule
        return rule

    def delete_assignment_rule(self, rule_id: UUID) -> None:
        self.assignment_rules.pop(rule_id, None)
