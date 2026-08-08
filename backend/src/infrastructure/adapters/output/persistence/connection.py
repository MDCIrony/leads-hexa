import os
from typing import Optional

import psycopg
from psycopg.rows import dict_row


class RawSqlDatabase:
    def __init__(self, dsn: Optional[str] = None) -> None:
        # No silent fallback to another database: that is exactly what let
        # this app run for a while writing to an unrelated in-memory SQLite
        # instance while a real Postgres container sat empty next to it.
        self.dsn = dsn or os.environ["DATABASE_URL"]

    def get_connection(self, autocommit: bool = False) -> psycopg.Connection:
        return psycopg.connect(self.dsn, row_factory=dict_row, autocommit=autocommit)

    def init_db(self) -> None:
        """Kept as the single entry point used by tests; the schema itself now
        lives in versioned .sql files."""
        from pathlib import Path

        from infrastructure.adapters.output.persistence.migration_runner import MigrationRunner

        migrations_dir = Path(__file__).resolve().parents[5] / "migrations"
        MigrationRunner(self, migrations_dir).apply_pending()

    def close(self) -> None:
        # Connections are opened per Unit of Work / per repository call
        # rather than cached on this object, so there is nothing to release.
        pass
