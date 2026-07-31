import json
import uuid
from typing import List
from uuid import UUID
from application.ports.output.rule_repository_port import RuleRepositoryPort
from domain.entities.rule import ScoringRule, RoutingRule
from domain.value_objects import Operator, AssignmentStrategy
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase

class RawSqlRuleRepository(RuleRepositoryPort):
    def __init__(self, db: RawSqlDatabase) -> None:
        self.db = db

    def get_scoring_rules_by_tenant(self, tenant_id: UUID) -> List[ScoringRule]:
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM scoring_rules WHERE tenant_id = ?", (str(tenant_id),))
        rows = cursor.fetchall()
        rules = []
        for r in rows:
            rules.append(
                ScoringRule(
                    id=uuid.UUID(r["id"]),
                    name=r["name"],
                    field=r["field"],
                    operator=Operator(r["operator"]),
                    value=json.loads(r["value"]),
                    score_delta=r["score_delta"],
                )
            )
        return rules

    def get_routing_rules_by_tenant(self, tenant_id: UUID) -> List[RoutingRule]:
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM routing_rules WHERE tenant_id = ?", (str(tenant_id),))
        rows = cursor.fetchall()
        rules = []
        for r in rows:
            target_ids = [uuid.UUID(i) for i in json.loads(r["target_agent_ids"])] if r["target_agent_ids"] else []
            rules.append(
                RoutingRule(
                    id=uuid.UUID(r["id"]),
                    min_score=r["min_score"],
                    target_team=r["target_team"],
                    assignment_strategy=AssignmentStrategy(r["assignment_strategy"]),
                    target_agent_ids=target_ids,
                )
            )
        return rules

    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO scoring_rules (id, tenant_id, name, field, operator, value, score_delta) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(rule.id),
                    str(tenant_id),
                    rule.name,
                    rule.field,
                    rule.operator.value,
                    json.dumps(rule.value),
                    rule.score_delta,
                ),
            )
        return rule

    def save_routing_rule(self, tenant_id: UUID, rule: RoutingRule) -> RoutingRule:
        conn = self.db.get_connection()
        target_ids_json = json.dumps([str(i) for i in rule.target_agent_ids])
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO routing_rules (id, tenant_id, min_score, target_team, assignment_strategy, target_agent_ids) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(rule.id),
                    str(tenant_id),
                    rule.min_score,
                    rule.target_team,
                    rule.assignment_strategy.value,
                    target_ids_json,
                ),
            )
        return rule
