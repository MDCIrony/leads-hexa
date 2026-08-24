from typing import List, Optional
from uuid import UUID

import psycopg

from application.ports.output.agent_repository_port import AgentRepositoryPort
from domain.entities.agent import Agent


class RawSqlAgentRepository(AgentRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def _row_to_agent(self, r) -> Agent:
        return Agent.create(
            agent_id=r["id"],
            name=r["name"],
            email=r["email"],
            group_id=r["group_id"],
            is_active=r["is_active"],
            role=r["role"],
            hashed_password=r["hashed_password"],
            tenant_id=r["tenant_id"],
        )

    def get_available_agents(self, tenant_id: UUID, group_id: Optional[UUID] = None) -> List[Agent]:
        # INTEGRATION excluded here and in list_by_tenant (ADR-0028): a machine
        # credential lives in `agents` to reuse the password hash and the
        # deactivation path, not because it is a person to route work to.
        sql = "SELECT * FROM agents WHERE tenant_id = %s AND is_active = TRUE AND role <> 'INTEGRATION'"
        params: list = [tenant_id]
        if group_id:
            sql += " AND group_id = %s"
            params.append(group_id)
        sql += " ORDER BY name, id"
        rows = self.connection.execute(sql, tuple(params)).fetchall()
        return [self._row_to_agent(r) for r in rows]

    def save(self, agent: Agent) -> Agent:
        self.connection.execute(
            """
            INSERT INTO agents (id, name, email, group_id, is_active, role, hashed_password, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                group_id = EXCLUDED.group_id,
                is_active = EXCLUDED.is_active,
                role = EXCLUDED.role,
                hashed_password = EXCLUDED.hashed_password,
                tenant_id = EXCLUDED.tenant_id
            """,
            (
                agent.id.value,
                agent.name,
                agent.email,
                agent.group_id.value if agent.group_id else None,
                agent.is_active,
                agent.role.value,
                agent.hashed_password,
                agent.tenant_id.value if agent.tenant_id else None,
            ),
        )
        return agent

    def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        cursor = self.connection.execute("SELECT * FROM agents WHERE id = %s", (agent_id,))
        r = cursor.fetchone()
        return self._row_to_agent(r) if r else None

    def list_active(self, group_id: Optional[UUID] = None, limit: int = 100, offset: int = 0) -> List[Agent]:
        if group_id:
            cursor = self.connection.execute(
                "SELECT * FROM agents WHERE is_active = TRUE AND group_id = %s ORDER BY id LIMIT %s OFFSET %s",
                (group_id, limit, offset),
            )
        else:
            cursor = self.connection.execute(
                "SELECT * FROM agents WHERE is_active = TRUE ORDER BY id LIMIT %s OFFSET %s",
                (limit, offset),
            )
        rows = cursor.fetchall()
        return [self._row_to_agent(r) for r in rows]

    def count_active(self, group_id: Optional[UUID] = None) -> int:
        if group_id:
            cursor = self.connection.execute(
                "SELECT COUNT(*) AS count FROM agents WHERE is_active = TRUE AND group_id = %s",
                (group_id,),
            )
        else:
            cursor = self.connection.execute(
                "SELECT COUNT(*) AS count FROM agents WHERE is_active = TRUE"
            )
        row = cursor.fetchone()
        return row["count"]

    def get_by_email(self, email: str) -> Optional[Agent]:
        cursor = self.connection.execute("SELECT * FROM agents WHERE email = %s", (email,))
        r = cursor.fetchone()
        return self._row_to_agent(r) if r else None

    def count(self) -> int:
        cursor = self.connection.execute("SELECT COUNT(*) AS total FROM agents")
        return cursor.fetchone()["total"]

    def list_by_tenant(
        self,
        tenant_id: UUID,
        group_id: Optional[UUID] = None,
        is_active: Optional[bool] = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Agent]:
        # role <> 'INTEGRATION' (ADR-0028): otherwise a machine credential
        # shows up in the manager's advisor template and can end up named in
        # an assignment rule, receiving leads nobody will work.
        sql = "SELECT * FROM agents WHERE tenant_id = %s AND role <> 'INTEGRATION'"
        params: list = [tenant_id]
        # is_active is not None, never just "if is_active": is_active=False
        # is falsy, and the naive form would silently drop the clause and
        # return everyone instead of only the deactivated agents.
        if is_active is not None:
            sql += " AND is_active = %s"
            params.append(is_active)
        if group_id:
            sql += " AND group_id = %s"
            params.append(group_id)
        # Explicit ordering: without it a page can repeat or skip rows.
        sql += " ORDER BY name, id LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        rows = self.connection.execute(sql, tuple(params)).fetchall()
        return [self._row_to_agent(row) for row in rows]

    def count_by_tenant(
        self, tenant_id: UUID, group_id: Optional[UUID] = None, is_active: Optional[bool] = True
    ) -> int:
        # Paired with list_by_tenant's same exclusion (ADR-0028): GetAgentsUseCase
        # calls both with identical filters, and a total that still counted the
        # INTEGRATION row would contradict a page that no longer lists it.
        sql = "SELECT COUNT(*) AS count FROM agents WHERE tenant_id = %s AND role <> 'INTEGRATION'"
        params: list = [tenant_id]
        if is_active is not None:
            sql += " AND is_active = %s"
            params.append(is_active)
        if group_id:
            sql += " AND group_id = %s"
            params.append(group_id)
        row = self.connection.execute(sql, tuple(params)).fetchone()
        return int(row["count"])

    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]:
        row = self.connection.execute(
            "SELECT * FROM agents WHERE id = %s AND tenant_id = %s",
            (agent_id, tenant_id),
        ).fetchone()
        return self._row_to_agent(row) if row else None

    def deactivate_all_by_tenant(self, tenant_id: UUID) -> int:
        cursor = self.connection.execute(
            "UPDATE agents SET is_active = FALSE WHERE tenant_id = %s AND is_active = TRUE",
            (tenant_id,),
        )
        return cursor.rowcount

    def distinct_tenant_ids(self) -> List[UUID]:
        # Not part of Task 5's literal spec (only declared abstract there,
        # for Task 7 to consume); implemented now because ABC requires every
        # concrete subclass to fill every abstract method immediately.
        rows = self.connection.execute(
            "SELECT DISTINCT tenant_id FROM agents WHERE tenant_id IS NOT NULL"
        ).fetchall()
        return [row["tenant_id"] for row in rows]
