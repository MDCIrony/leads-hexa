"""Fills `advisors` from `agents` for tests that create agents but run no worker.

In the running stack the consumer of internal.identity.agents writes the
identity columns; until C2 nothing writes `advisors.group_id`, so this copies
the group that the old `/agents` path stored too."""


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
