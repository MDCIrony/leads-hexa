from typing import Any, List, Optional
from uuid import UUID

import psycopg

from application.ports.output.advisors.advisor_repository_port import AdvisorRepositoryPort
from domain.advisors.advisor import Advisor
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId

# ADR-0028: a machine credential is an agent row for identity, never a person to route work to.
_ROUTABLE = "tenant_id = %s AND role <> 'INTEGRATION'"


class RawSqlAdvisorRepository(AdvisorRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    @staticmethod
    def _to_advisor(row) -> Advisor:
        return Advisor(
            agent_id=AgentId(row["agent_id"]),
            tenant_id=TenantId(row["tenant_id"]),
            name=row["name"],
            role=AgentRole(row["role"]),
            is_active=row["is_active"],
            version=row["version"],
            group_id=GroupId(row["group_id"]) if row["group_id"] else None,
        )

    def get(self, agent_id: UUID, tenant_id: UUID) -> Optional[Advisor]:
        row = self.connection.execute(
            "SELECT * FROM advisors WHERE agent_id = %s AND tenant_id = %s", (agent_id, tenant_id)
        ).fetchone()
        return self._to_advisor(row) if row else None

    def list_available(self, tenant_id: UUID, group_id: Optional[UUID] = None) -> List[Advisor]:
        sql = "SELECT * FROM advisors WHERE " + _ROUTABLE + " AND is_active"
        params: List[Any] = [tenant_id]
        if group_id is not None:
            sql += " AND group_id = %s"
            params.append(group_id)
        rows = self.connection.execute(sql + " ORDER BY name, agent_id", tuple(params)).fetchall()
        return [self._to_advisor(row) for row in rows]

    def list(
        self,
        tenant_id: UUID,
        group_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Advisor]:
        sql = "SELECT * FROM advisors WHERE " + _ROUTABLE
        params: List[Any] = [tenant_id]
        if group_id is not None:
            sql += " AND group_id = %s"
            params.append(group_id)
        # `is not None`, not truthiness: is_active=False must filter, not vanish.
        if is_active is not None:
            sql += " AND is_active = %s"
            params.append(is_active)
        sql += " ORDER BY name, agent_id LIMIT %s OFFSET %s"
        rows = self.connection.execute(sql, (*params, limit, offset)).fetchall()
        return [self._to_advisor(row) for row in rows]

    def count_by_group(self, tenant_id: UUID, group_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM advisors WHERE " + _ROUTABLE + " AND is_active AND group_id = %s",
            (tenant_id, group_id),
        ).fetchone()
        return int(row["count"])

    def upsert_identity(self, advisor: Advisor) -> None:
        # Gated in SQL as well as by Advisor.supersedes: two writers (a zombie
        # consumer after a rebalance, a second replica) can both pass the read
        # check, and the loser must not overwrite a newer committed version.
        # group_id is absent from both lists on purpose.
        self.connection.execute(
            """
            INSERT INTO advisors (agent_id, tenant_id, name, role, is_active, version)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (agent_id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                name = EXCLUDED.name,
                role = EXCLUDED.role,
                is_active = EXCLUDED.is_active,
                version = EXCLUDED.version
            WHERE advisors.version < EXCLUDED.version
            """,
            (advisor.agent_id.value, advisor.tenant_id.value, advisor.name, advisor.role.value,
             advisor.is_active, advisor.version),
        )

    def set_group(self, agent_id: UUID, tenant_id: UUID, group_id: Optional[UUID]) -> bool:
        cursor = self.connection.execute(
            "UPDATE advisors SET group_id = %s WHERE agent_id = %s AND tenant_id = %s",
            (group_id, agent_id, tenant_id),
        )
        return cursor.rowcount == 1
