import os
from typing import Optional

import psycopg
from psycopg.rows import dict_row

# Each statement is executed separately (rather than as one multi-statement
# script) because psycopg's extended query protocol does not support
# multiple commands in a single execute() call.
CREATE_TABLES_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL,
        company TEXT NOT NULL,
        budget DOUBLE PRECISION NOT NULL,
        industry TEXT NOT NULL,
        custom_attributes TEXT,
        phone TEXT,
        score INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        assigned_agent_id TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scoring_rules (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        name TEXT NOT NULL,
        field TEXT NOT NULL,
        operator TEXT NOT NULL,
        value TEXT NOT NULL,
        score_delta INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS routing_rules (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        min_score INTEGER NOT NULL,
        target_team TEXT NOT NULL,
        assignment_strategy TEXT NOT NULL,
        target_agent_ids TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        team TEXT NOT NULL,
        active_leads_count INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    ALTER TABLE agents ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'AGENT'
    """,
    """
    ALTER TABLE agents ADD COLUMN IF NOT EXISTS hashed_password TEXT
    """,
    """
    ALTER TABLE agents ADD COLUMN IF NOT EXISTS tenant_id TEXT
    """,
    """
    CREATE TABLE IF NOT EXISTS webhook_configs (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        target_url TEXT NOT NULL,
        secret_token TEXT NOT NULL
    )
    """,
]


class RawSqlDatabase:
    def __init__(self, dsn: Optional[str] = None) -> None:
        # No silent fallback to another database: that is exactly what let
        # this app run for a while writing to an unrelated in-memory SQLite
        # instance while a real Postgres container sat empty next to it.
        self.dsn = dsn or os.environ["DATABASE_URL"]

    def get_connection(self, autocommit: bool = False) -> psycopg.Connection:
        return psycopg.connect(self.dsn, row_factory=dict_row, autocommit=autocommit)

    def init_db(self) -> None:
        conn = self.get_connection(autocommit=True)
        try:
            with conn.cursor() as cursor:
                for statement in CREATE_TABLES_STATEMENTS:
                    cursor.execute(statement)
        finally:
            conn.close()

    def close(self) -> None:
        # Connections are opened per Unit of Work / per repository call
        # rather than cached on this object, so there is nothing to release.
        pass
