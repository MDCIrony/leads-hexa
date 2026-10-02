from pathlib import Path
from typing import List

from chassis.persistence.database import RawSqlDatabase

_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


class MigrationRunner:
    """Applies numbered .sql files once each, in filename order.

    Deliberately not Alembic: that would pull in SQLAlchemy, which this project
    rules out."""

    def __init__(self, database: RawSqlDatabase, migrations_dir: Path) -> None:
        self._database = database
        self._migrations_dir = Path(migrations_dir)

    def apply_pending(self) -> List[str]:
        applied: List[str] = []
        with self._database.get_connection(autocommit=True) as conn:
            conn.execute(_TRACKING_TABLE)
            rows = conn.execute("SELECT name FROM schema_migrations").fetchall()
            already_applied = {row["name"] for row in rows}

            for path in sorted(self._migrations_dir.glob("*.sql")):
                if path.name in already_applied:
                    continue
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
                )
                applied.append(path.name)
        return applied
