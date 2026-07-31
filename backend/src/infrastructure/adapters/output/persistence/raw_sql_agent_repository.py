from typing import List, Optional
from uuid import UUID
from application.ports.output.agent_repository_port import AgentRepositoryPort
from domain.entities.agent import Agent
from domain.value_objects import AgentId
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase

class RawSqlAgentRepository(AgentRepositoryPort):
    def __init__(self, db: RawSqlDatabase) -> None:
        self.db = db

    def get_available_agents(self, team: Optional[str] = None) -> List[Agent]:
        conn = self.db.get_connection()
        if team:
            cursor = conn.execute("SELECT * FROM agents WHERE is_active = 1 AND team = ?", (team,))
        else:
            cursor = conn.execute("SELECT * FROM agents WHERE is_active = 1")
        rows = cursor.fetchall()
        return [
            Agent(
                id=AgentId(r["id"]),
                name=r["name"],
                email=r["email"],
                team=r["team"],
                active_leads_count=r["active_leads_count"],
                is_active=bool(r["is_active"]),
            )
            for r in rows
        ]

    def update_active_count(self, agent_id: UUID, new_count: int) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                "UPDATE agents SET active_leads_count = ? WHERE id = ?",
                (new_count, str(agent_id)),
            )

    def save(self, agent: Agent) -> Agent:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
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
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (str(agent_id),))
        r = cursor.fetchone()
        if not r:
            return None
        return Agent(
            id=AgentId(r["id"]),
            name=r["name"],
            email=r["email"],
            team=r["team"],
            active_leads_count=r["active_leads_count"],
            is_active=bool(r["is_active"]),
        )
