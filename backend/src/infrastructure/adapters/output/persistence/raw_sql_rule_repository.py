from typing import List
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.rule_repository_port import RuleRepositoryPort
from domain.entities.rule import AssignmentRule, ScoringRule


class RawSqlRuleRepository(RuleRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        cursor = self.connection.execute(
            "SELECT * FROM scoring_rules WHERE tenant_id = %s", (tenant_id,)
        )
        rows = cursor.fetchall()
        rules = []
        for r in rows:
            rules.append(
                ScoringRule.create(
                    rule_id=r["id"],
                    name=r["name"],
                    field=r["field"],
                    operator=r["operator"],
                    value=r["value"],
                    score_delta=r["score_delta"],
                )
            )
        return rules

    def get_assignment_rules_by_tenant(self, tenant_id: UUID) -> List[AssignmentRule]:
        rows = self.connection.execute(
            "SELECT * FROM assignment_rules WHERE tenant_id = %s ORDER BY priority DESC, id",
            (tenant_id,),
        ).fetchall()
        return [self._to_assignment_rule(row) for row in rows]

    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        self.connection.execute(
            """
            INSERT INTO scoring_rules (id, tenant_id, name, field, operator, value, score_delta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                name = EXCLUDED.name,
                field = EXCLUDED.field,
                operator = EXCLUDED.operator,
                value = EXCLUDED.value,
                score_delta = EXCLUDED.score_delta
            """,
            (
                rule.id,
                tenant_id,
                rule.name,
                rule.field,
                rule.operator.value,
                Jsonb(rule.value),
                rule.score_delta,
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
                is_active, rr_cursor
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                rr_cursor = EXCLUDED.rr_cursor
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
        )
