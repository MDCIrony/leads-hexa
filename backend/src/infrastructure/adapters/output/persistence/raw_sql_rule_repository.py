from typing import List, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.rules.rule_repository_port import RuleRepositoryPort
from domain.rules.assignment_rule import AssignmentRule
from domain.rules.scoring_rule import ScoringRule

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
        return [self._to_scoring_rule(row) for row in rows]

    def get_scoring_rule_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[ScoringRule]:
        row = self.connection.execute(
            "SELECT * FROM scoring_rules WHERE id = %s AND tenant_id = %s",
            (rule_id, tenant_id),
        ).fetchone()
        return self._to_scoring_rule(row) if row else None

    def list_scoring_rules_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[ScoringRule]:
        rows = self.connection.execute(
            "SELECT * FROM scoring_rules WHERE tenant_id = %s "
            "ORDER BY priority DESC, id LIMIT %s OFFSET %s",
            (tenant_id, limit, offset),
        ).fetchall()
        return [self._to_scoring_rule(row) for row in rows]

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

    @staticmethod
    def _to_scoring_rule(row) -> ScoringRule:
        return ScoringRule.create(
            tenant_id=row["tenant_id"],
            rule_id=row["id"],
            name=row["name"],
            conditions=row["conditions"] or [],
            score_delta=row["score_delta"],
            priority=row["priority"],
            is_active=row["is_active"],
        )

    def get_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        rows = self.connection.execute(
            "SELECT * FROM assignment_rules WHERE tenant_id = %s ORDER BY priority DESC, id",
            (tenant_id,),
        ).fetchall()
        return [self._to_assignment_rule(row) for row in rows]

    def lock_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        # Same ORDER BY as the unlocked read, and that is what keeps this
        # deadlock-free: every transaction takes the rows in one order.
        rows = self.connection.execute(
            "SELECT * FROM assignment_rules WHERE tenant_id = %s ORDER BY priority DESC, id FOR UPDATE",
            (tenant_id,),
        ).fetchall()
        return [self._to_assignment_rule(row) for row in rows]

    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        self.connection.execute(
            """
            INSERT INTO scoring_rules (
                id, tenant_id, name, conditions, score_delta, priority, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                name = EXCLUDED.name,
                conditions = EXCLUDED.conditions,
                score_delta = EXCLUDED.score_delta,
                priority = EXCLUDED.priority,
                is_active = EXCLUDED.is_active
            """,
            (
                rule.id,
                tenant_id,
                rule.name,
                Jsonb([c.as_dict() for c in rule.conditions]),
                rule.score_delta,
                rule.priority,
                rule.is_active,
            ),
        )
        return rule

    def save_assignment_rule(self, tenant_id: UUID, rule: AssignmentRule) -> AssignmentRule:
        # rr_cursor is written on every save: skipping it is exactly the bug
        # this phase fixes, since round-robin would reset on every request.
        target_ids = Jsonb([str(i) for i in rule.target_agent_ids])
        self.connection.execute(
            """
            INSERT INTO assignment_rules (
                id, tenant_id, name, min_score, max_score, target_group_id,
                target_agent_ids, agent_match_mode, strategy, priority,
                is_active, rr_cursor, conditions
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                min_score = EXCLUDED.min_score,
                max_score = EXCLUDED.max_score,
                target_group_id = EXCLUDED.target_group_id,
                target_agent_ids = EXCLUDED.target_agent_ids,
                agent_match_mode = EXCLUDED.agent_match_mode,
                strategy = EXCLUDED.strategy,
                priority = EXCLUDED.priority,
                is_active = EXCLUDED.is_active,
                rr_cursor = EXCLUDED.rr_cursor,
                conditions = EXCLUDED.conditions
            """,
            (
                rule.id,
                tenant_id,
                rule.name,
                rule.min_score,
                rule.max_score,
                rule.target_group_id,
                target_ids,
                rule.agent_match_mode.value,
                rule.strategy.value if rule.strategy else None,
                rule.priority,
                rule.is_active,
                rule.rr_cursor,
                Jsonb([c.as_dict() for c in rule.conditions]),
            ),
        )
        return rule

    def delete_assignment_rule(self, rule_id: UUID) -> None:
        self.connection.execute("DELETE FROM assignment_rules WHERE id = %s", (rule_id,))

    @staticmethod
    def _to_assignment_rule(row) -> AssignmentRule:
        # restore(), not create(): a rule whose group was deleted is a valid
        # stored state, and create() would refuse to read it back.
        return AssignmentRule.restore(
            rule_id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            min_score=row["min_score"],
            max_score=row["max_score"],
            target_group_id=row["target_group_id"],
            target_agent_ids=row["target_agent_ids"],
            agent_match_mode=row["agent_match_mode"],
            strategy=row["strategy"],
            priority=row["priority"],
            is_active=row["is_active"],
            rr_cursor=row["rr_cursor"],
            conditions=row["conditions"] or [],
        )
