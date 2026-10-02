import os
from pathlib import Path
from typing import Optional

from chassis.persistence import MigrationRunner, RawSqlDatabase as ChassisRawSqlDatabase


class RawSqlDatabase(ChassisRawSqlDatabase):
    """The shared pool, defaulting its DSN to DATABASE_URL.

    Still no fallback to another database: a missing variable raises KeyError."""

    def __init__(self, dsn: Optional[str] = None, min_size: int = 1, max_size: int = 10) -> None:
        super().__init__(dsn or os.environ["DATABASE_URL"], min_size, max_size)

    def init_db(self) -> None:
        """Kept as the single entry point used by tests; the schema itself now
        lives in versioned .sql files."""
        migrations_dir = Path(__file__).resolve().parents[5] / "migrations"
        MigrationRunner(self, migrations_dir).apply_pending()
