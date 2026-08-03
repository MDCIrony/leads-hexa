from typing import List, Optional
from uuid import UUID
import sqlite3

from application.ports.output.agent_repository_port import AgentRepositoryPort
from domain.entities.agent import Agent

class RawSqlAgentRepository(AgentRepositoryPort):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_available_agents(self, team: Optional[str] = None) -> List[Agent]:
        if team:
            cursor = self.connection.execute("SELECT * FROM agents WHERE is_active = 1 AND team = ?", (team,))
        else:
            cursor = self.connection.execute("SELECT * FROM agents WHERE is_active = 1")
        rows = cursor.fetchall()
        return [
            Agent.create(
                agent_id=r["id"],
                name=r["name"],
                email=r["email"],
                team=r["team"],
                active_leads_count=r["active_leads_count"],
                is_active=bool(r["is_active"]),
            )
            for r in rows
        ]

    def update_active_count(self, agent_id: UUID, new_count: int) -> None:
        self.connection.execute(
            "UPDATE agents SET active_leads_count = ? WHERE id = ?",
            (new_count, str(agent_id)),
        )

    def save(self, agent: Agent) -> Agent:
        self.connection.execute(
            "INSERT OR REPLACE INTO agents (id, name, email, team, active_leads_count, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(agent.id),
                agent.name,
                agent.email,
                agent.team,
                agent.active_leads_count,
                1 if agent.is_active else 0,
            ),
        )
        return agent

    def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        cursor = self.connection.execute("SELECT * FROM agents WHERE id = ?", (str(agent_id),))
        r = cursor.fetchone()
        if not r:
            return None
        return Agent.create(
            agent_id=r["id"],
            name=r["name"],
            email=r["email"],
            team=r["team"],
            active_leads_count=r["active_leads_count"],
            is_active=bool(r["is_active"]),
        )
