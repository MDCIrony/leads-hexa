from typing import List, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.disqualification_rule_repository_port import (
    DisqualificationRuleRepositoryPort,
)
from domain.entities.disqualification_rule import DisqualificationRule


class RawSqlDisqualificationRuleRepository(DisqualificationRuleRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, rule: DisqualificationRule) -> DisqualificationRule:
        self.connection.execute(
            """
            INSERT INTO disqualification_rules (
                id, tenant_id, name, conditions, priority, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                conditions = EXCLUDED.conditions,
                priority = EXCLUDED.priority,
                is_active = EXCLUDED.is_active
            """,
            (
                rule.id,
                rule.tenant_id,
                rule.name,
                Jsonb([c.as_dict() for c in rule.conditions]),
                rule.priority,
                rule.is_active,
            ),
        )
        return rule

    def get_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[DisqualificationRule]:
        row = self.connection.execute(
            "SELECT * FROM disqualification_rules WHERE id = %s AND tenant_id = %s",
            (rule_id, tenant_id),
        ).fetchone()
        return self._to_rule(row) if row else None

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[DisqualificationRule]:
        rows = self.connection.execute(
            "SELECT * FROM disqualification_rules WHERE tenant_id = %s "
            "ORDER BY priority DESC, id LIMIT %s OFFSET %s",
            (tenant_id, limit, offset),
        ).fetchall()
        return [self._to_rule(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM disqualification_rules WHERE tenant_id = %s",
            (tenant_id,),
        ).fetchone()
        return int(row["count"])

    def delete(self, rule_id: UUID, tenant_id: UUID) -> bool:
        # Filtered inside the DELETE itself, not just checked beforehand: the
        # difference from delete_assignment_rule, which trusts the caller to
        # have verified ownership first.
        cursor = self.connection.execute(
            "DELETE FROM disqualification_rules WHERE id = %s AND tenant_id = %s",
            (rule_id, tenant_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def _to_rule(row) -> DisqualificationRule:
        return DisqualificationRule.create(
            rule_id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            conditions=row["conditions"] or [],
            priority=row["priority"],
            is_active=row["is_active"],
        )
