"""Stand-ins for identity in tests that create agents through the monolith and run no worker.

In the running stack the consumer of internal.identity.agents writes the
identity columns and `PATCH /advisors` the group; `project_agents` copies both
from `agents`, the group being what the old `/agents` path stored.
`IdentityFromAgentsTable` answers hydration the way identity will, from the
same table: until the cut the monolith is where agents live."""
import psycopg
from psycopg.rows import dict_row

from application.ports.output.advisors.identity_agents_port import IdentityAgentsPort
from domain.advisors.advisor import Advisor
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.tenant_id import TenantId


def project_agents(connection) -> None:
    connection.execute(
        """
        INSERT INTO advisors (agent_id, tenant_id, name, role, is_active, version, group_id)
        SELECT id, tenant_id, name, role, is_active, version, group_id FROM agents
        WHERE tenant_id IS NOT NULL
        ON CONFLICT (agent_id) DO UPDATE SET
            tenant_id = EXCLUDED.tenant_id, name = EXCLUDED.name, role = EXCLUDED.role,
            is_active = EXCLUDED.is_active, version = EXCLUDED.version, group_id = EXCLUDED.group_id
        """
    )


def project_agents_of(database) -> None:
    with database.get_connection(autocommit=True) as connection:
        project_agents(connection)


class IdentityFromAgentsTable(IdentityAgentsPort):
    """Takes HttpIdentityAgents' arguments so the Container builds it unchanged."""

    dsn = ""

    def __init__(self, *_args, **_kwargs) -> None:
        self.calls = 0

    def fetch(self, agent_id):
        self.calls += 1
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            row = connection.execute("SELECT * FROM agents WHERE id = %s", (agent_id,)).fetchone()
        if row is None or row["tenant_id"] is None:
            return None
        return Advisor(AgentId(row["id"]), TenantId(row["tenant_id"]), row["name"], AgentRole(row["role"]),
                       row["is_active"], row["version"])
