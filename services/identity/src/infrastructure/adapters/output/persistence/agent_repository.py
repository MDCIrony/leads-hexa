from uuid import UUID

import psycopg

from application.ports.output.agents import AgentRepositoryPort
from domain.agents.agent import Agent

# ADR-0028: a machine credential lives in `agents` to reuse the password hash and the
# deactivation path, not to show up in the manager's advisor list or its total.
_TENANT_FILTER = "tenant_id = %s AND role <> 'INTEGRATION'"


def _to_agent(row) -> Agent:
    return Agent.create(
        row["name"],
        row["email"],
        agent_id=row["id"],
        is_active=row["is_active"],
        role=row["role"],
        hashed_password=row["hashed_password"],
        tenant_id=row["tenant_id"],
        version=row["version"],
    )


def _tenant_clause(tenant_id: UUID, is_active: bool | None) -> tuple[str, list]:
    clause, params = _TENANT_FILTER, [tenant_id]
    # `is not None`, never truthiness: is_active=False must filter, not vanish.
    if is_active is not None:
        clause += " AND is_active = %s"
        params.append(is_active)
    return clause, params


class PostgresAgentRepository(AgentRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, agent: Agent) -> Agent:
        row = self.connection.execute(
            """
            INSERT INTO agents (id, name, email, is_active, role, hashed_password, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                is_active = EXCLUDED.is_active,
                role = EXCLUDED.role,
                hashed_password = EXCLUDED.hashed_password,
                tenant_id = EXCLUDED.tenant_id,
                version = agents.version + 1
            RETURNING version
            """,
            (
                agent.id.value,
                agent.name,
                agent.email,
                agent.is_active,
                agent.role.value,
                agent.hashed_password,
                agent.tenant_id.value if agent.tenant_id else None,
            ),
        ).fetchone()
        agent.version = row["version"]
        return agent

    def get_by_id(self, agent_id: UUID) -> Agent | None:
        row = self.connection.execute("SELECT * FROM agents WHERE id = %s", (agent_id,)).fetchone()
        return _to_agent(row) if row else None

    def get_by_email(self, email: str) -> Agent | None:
        # lower() on both sides is what idx_agents_email_normalized indexes.
        row = self.connection.execute(
            "SELECT * FROM agents WHERE lower(email) = lower(%s)", (email,)
        ).fetchone()
        return _to_agent(row) if row else None

    def count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) AS total FROM agents").fetchone()["total"]

    def list_by_tenant(
        self, tenant_id: UUID, is_active: bool | None = True, limit: int = 100, offset: int = 0
    ) -> list[Agent]:
        clause, params = _tenant_clause(tenant_id, is_active)
        # Explicit ordering: without it a page can repeat or skip rows.
        rows = self.connection.execute(
            "SELECT * FROM agents WHERE " + clause + " ORDER BY name, id LIMIT %s OFFSET %s",
            (*params, limit, offset),
        ).fetchall()
        return [_to_agent(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID, is_active: bool | None = True) -> int:
        clause, params = _tenant_clause(tenant_id, is_active)
        row = self.connection.execute("SELECT COUNT(*) AS total FROM agents WHERE " + clause, params).fetchone()
        return int(row["total"])

    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Agent | None:
        row = self.connection.execute(
            "SELECT * FROM agents WHERE id = %s AND tenant_id = %s", (agent_id, tenant_id)
        ).fetchone()
        return _to_agent(row) if row else None

    def deactivate_all_by_tenant(self, tenant_id: UUID) -> list[Agent]:
        rows = self.connection.execute(
            "UPDATE agents SET is_active = FALSE, version = version + 1"
            " WHERE tenant_id = %s AND is_active = TRUE RETURNING *",
            (tenant_id,),
        ).fetchall()
        return [_to_agent(row) for row in rows]

    def distinct_tenant_ids(self) -> list[UUID]:
        rows = self.connection.execute(
            "SELECT DISTINCT tenant_id FROM agents WHERE tenant_id IS NOT NULL ORDER BY tenant_id"
        ).fetchall()
        return [row["tenant_id"] for row in rows]

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Agent]:
        rows = self.connection.execute(
            "SELECT * FROM agents ORDER BY id LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()
        return [_to_agent(row) for row in rows]
