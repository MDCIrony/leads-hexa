from typing import List, Optional
from uuid import UUID

import psycopg

from application.ports.output.rules.rule_repository_port import RuleRepositoryPort
from domain.rules.assignment_rule import AssignmentRule
from domain.rules.scoring_rule import ScoringRule
from infrastructure.adapters.output.persistence.rules.rule_rows import (
    save_assignment_rule,
    save_scoring_rule,
    to_assignment_rule,
    to_scoring_rule,
)


class RawSqlRuleRepository(RuleRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        # ORDER BY added here too: without it, paginating list_scoring_rules_by_tenant
        # against the same table with no stable order could repeat or skip rows.
        cursor = self.connection.execute(
            "SELECT * FROM scoring_rules WHERE tenant_id = %s ORDER BY priority DESC, id",
            (tenant_id,),
        )
        rows = cursor.fetchall()
        return [to_scoring_rule(row) for row in rows]

    def get_scoring_rule_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[ScoringRule]:
        row = self.connection.execute(
            "SELECT * FROM scoring_rules WHERE id = %s AND tenant_id = %s",
            (rule_id, tenant_id),
        ).fetchone()
        return to_scoring_rule(row) if row else None

    def list_scoring_rules_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[ScoringRule]:
        rows = self.connection.execute(
            "SELECT * FROM scoring_rules WHERE tenant_id = %s "
            "ORDER BY priority DESC, id LIMIT %s OFFSET %s",
            (tenant_id, limit, offset),
        ).fetchall()
        return [to_scoring_rule(row) for row in rows]

    def count_scoring_rules_by_tenant(self, tenant_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM scoring_rules WHERE tenant_id = %s",
            (tenant_id,),
        ).fetchone()
        return int(row["count"])

    def delete_scoring_rule(self, rule_id: UUID, tenant_id: UUID) -> bool:
        # Filtered inside the DELETE itself, same double-key convention as
        # RawSqlDisqualificationRuleRepository.delete.
        cursor = self.connection.execute(
            "DELETE FROM scoring_rules WHERE id = %s AND tenant_id = %s",
            (rule_id, tenant_id),
        )
        return cursor.rowcount > 0

    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        return save_scoring_rule(self.connection, tenant_id, rule)

    def get_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        rows = self.connection.execute(
            "SELECT * FROM assignment_rules WHERE tenant_id = %s ORDER BY priority DESC, id",
            (tenant_id,),
        ).fetchall()
        return [to_assignment_rule(row) for row in rows]

    def lock_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        # Same ORDER BY as the unlocked read, and that is what keeps this
        # deadlock-free: every transaction takes the rows in one order.
        rows = self.connection.execute(
            "SELECT * FROM assignment_rules WHERE tenant_id = %s ORDER BY priority DESC, id FOR UPDATE",
            (tenant_id,),
        ).fetchall()
        return [to_assignment_rule(row) for row in rows]

    def save_assignment_rule(self, tenant_id: UUID, rule: AssignmentRule) -> AssignmentRule:
        return save_assignment_rule(self.connection, tenant_id, rule)

    def delete_assignment_rule(self, rule_id: UUID) -> None:
        self.connection.execute("DELETE FROM assignment_rules WHERE id = %s", (rule_id,))
