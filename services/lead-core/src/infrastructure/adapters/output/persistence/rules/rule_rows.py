"""Scoring and assignment rules to and from their rows."""
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from domain.rules.assignment_rule import AssignmentRule
from domain.rules.scoring_rule import ScoringRule


def save_scoring_rule(connection: psycopg.Connection, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
    connection.execute(
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


def to_scoring_rule(row) -> ScoringRule:
    return ScoringRule.create(
        tenant_id=row["tenant_id"],
        rule_id=row["id"],
        name=row["name"],
        conditions=row["conditions"] or [],
        score_delta=row["score_delta"],
        priority=row["priority"],
        is_active=row["is_active"],
    )


def save_assignment_rule(connection: psycopg.Connection, tenant_id: UUID, rule: AssignmentRule) -> AssignmentRule:
    # rr_cursor is written on every save: skipping it is exactly the bug
    # this phase fixes, since round-robin would reset on every request.
    target_ids = Jsonb([str(i) for i in rule.target_agent_ids])
    connection.execute(
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


def to_assignment_rule(row) -> AssignmentRule:
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
