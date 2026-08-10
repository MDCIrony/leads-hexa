from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from domain.entities.rule import AssignmentRule, ScoringRule

class RuleRepositoryPort(ABC):
    @abstractmethod
    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        pass

    @abstractmethod
    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        pass

    # Prefixed with scoring_ (unlike DisqualificationRuleRepositoryPort's
    # bare names) because this port is shared with assignment rules.
    @abstractmethod
    def get_scoring_rule_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[ScoringRule]:
        pass

    @abstractmethod
    def list_scoring_rules_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[ScoringRule]:
        pass

    @abstractmethod
    def count_scoring_rules_by_tenant(self, tenant_id: UUID) -> int:
        pass

    @abstractmethod
    def delete_scoring_rule(self, rule_id: UUID, tenant_id: UUID) -> bool:
        pass

    @abstractmethod
    def get_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        """Return every assignment rule of this organization."""

    @abstractmethod
    def save_assignment_rule(self, tenant_id: UUID, rule: AssignmentRule) -> AssignmentRule:
        """Insert or update a rule, including its rotation cursor.

        Skipping rr_cursor here is the bug this phase fixes: round-robin
        would reset to the start on every request instead of rotating."""

    @abstractmethod
    def delete_assignment_rule(self, rule_id: UUID) -> None:
        pass
