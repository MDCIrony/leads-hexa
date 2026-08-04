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
            team=r["team"],
            active_leads_count=r["active_leads_count"],
            is_active=bool(r["is_active"]),
            role=r["role"],
            hashed_password=r["hashed_password"],
            tenant_id=r["tenant_id"],
        )

    def get_available_agents(self, team: Optional[str] = None) -> List[Agent]:
        if team:
            cursor = self.connection.execute(
                "SELECT * FROM agents WHERE is_active = 1 AND team = %s", (team,)
            )
        else:
            cursor = self.connection.execute("SELECT * FROM agents WHERE is_active = 1")
        rows = cursor.fetchall()
        return [self._row_to_agent(r) for r in rows]

    def update_active_count(self, agent_id: UUID, new_count: int) -> None:
        self.connection.execute(
            "UPDATE agents SET active_leads_count = %s WHERE id = %s",
            (new_count, str(agent_id)),
        )

    def save(self, agent: Agent) -> Agent:
        self.connection.execute(
            """
            INSERT INTO agents (id, name, email, team, active_leads_count, is_active, role, hashed_password, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                team = EXCLUDED.team,
                active_leads_count = EXCLUDED.active_leads_count,
                is_active = EXCLUDED.is_active,
                role = EXCLUDED.role,
                hashed_password = EXCLUDED.hashed_password,
                tenant_id = EXCLUDED.tenant_id
            """,
            (
                str(agent.id),
                agent.name,
                agent.email,
                agent.team,
                agent.active_leads_count,
                1 if agent.is_active else 0,
                agent.role.value,
                agent.hashed_password,
                str(agent.tenant_id) if agent.tenant_id else None,
            ),
        )
        return agent

    def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        cursor = self.connection.execute("SELECT * FROM agents WHERE id = %s", (str(agent_id),))
        r = cursor.fetchone()
        return self._row_to_agent(r) if r else None

    def list_active(self, team: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Agent]:
        if team:
            cursor = self.connection.execute(
                "SELECT * FROM agents WHERE is_active = 1 AND team = %s ORDER BY id LIMIT %s OFFSET %s",
                (team, limit, offset),
            )
        else:
            cursor = self.connection.execute(
                "SELECT * FROM agents WHERE is_active = 1 ORDER BY id LIMIT %s OFFSET %s",
                (limit, offset),
            )
        rows = cursor.fetchall()
        return [self._row_to_agent(r) for r in rows]

    def count_active(self, team: Optional[str] = None) -> int:
        if team:
            cursor = self.connection.execute(
                "SELECT COUNT(*) AS count FROM agents WHERE is_active = 1 AND team = %s",
                (team,),
            )
        else:
            cursor = self.connection.execute(
                "SELECT COUNT(*) AS count FROM agents WHERE is_active = 1"
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
