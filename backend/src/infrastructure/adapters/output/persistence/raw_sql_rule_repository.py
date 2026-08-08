import json
from typing import List
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.rule_repository_port import RuleRepositoryPort
from domain.entities.rule import RoutingRule, ScoringRule


class RawSqlRuleRepository(RuleRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        # value stays TEXT+JSON-encoded, not JSONB: it holds whatever scalar
        # type a rule compares against (str/int/bool), decided per row, which
        # is exactly what json.dumps/loads are for, independent of this
        # migration's id/date/attribute/flag scope.
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
                    value=json.loads(r["value"]),
                    score_delta=r["score_delta"],
                )
            )
        return rules

    def get_routing_rules_by_tenant(self, tenant_id: UUID) -> List[RoutingRule]:
        cursor = self.connection.execute(
            "SELECT * FROM routing_rules WHERE tenant_id = %s", (tenant_id,)
        )
        rows = cursor.fetchall()
        rules = []
        for r in rows:
            target_ids = r["target_agent_ids"]
            rules.append(
                RoutingRule.create(
                    rule_id=r["id"],
                    min_score=r["min_score"],
                    target_team=r["target_team"],
                    assignment_strategy=r["assignment_strategy"],
                    target_agent_ids=target_ids,
                )
            )
        return rules

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
                json.dumps(rule.value),
                rule.score_delta,
            ),
        )
        return rule

    def save_routing_rule(self, tenant_id: UUID, rule: RoutingRule) -> RoutingRule:
        # UUIDs still need stringifying here: JSON has no UUID type of its
        # own, so this is serialization for the jsonb array, not the manual
        # id-column translation the migration removes elsewhere.
        target_ids = Jsonb([str(i) for i in rule.target_agent_ids])
        self.connection.execute(
            """
            INSERT INTO routing_rules (id, tenant_id, min_score, target_team, assignment_strategy, target_agent_ids)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                min_score = EXCLUDED.min_score,
                target_team = EXCLUDED.target_team,
                assignment_strategy = EXCLUDED.assignment_strategy,
                target_agent_ids = EXCLUDED.target_agent_ids
            """,
            (
                rule.id,
                tenant_id,
                rule.min_score,
                rule.target_team,
                rule.assignment_strategy.value,
                target_ids,
            ),
        )
        return rule
