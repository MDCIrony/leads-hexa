from pathlib import Path

from chassis.persistence import MigrationRunner
from tests.integration.schema.tables import FOREIGN_TABLES, LEAD_CORE_TABLES, tables_in

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def test_applies_every_migration_on_a_fresh_database(test_db):
    # test_db already ran init_db() (now the runner itself) at fixture setup,
    # so schema_migrations already has 001 recorded. Drop it to reproduce the
    # actual first-boot state this test is named for: tracking table absent,
    # data tables already there.
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS schema_migrations")

    applied = MigrationRunner(test_db, _MIGRATIONS_DIR).apply_pending()
    assert "001_baseline_schema.sql" in applied


def test_is_idempotent(test_db):
    """Running twice must be a no-op, or every container restart would fail."""
    runner = MigrationRunner(test_db, _MIGRATIONS_DIR)
    runner.apply_pending()
    assert runner.apply_pending() == []


def test_records_what_it_applied(test_db):
    MigrationRunner(test_db, _MIGRATIONS_DIR).apply_pending()
    with test_db.get_connection(autocommit=True) as conn:
        rows = conn.execute("SELECT name FROM schema_migrations ORDER BY name").fetchall()
    assert [row["name"] for row in rows] == sorted(
        path.name for path in _MIGRATIONS_DIR.glob("*.sql")
    )


def test_creates_the_expected_tables(test_db):
    MigrationRunner(test_db, _MIGRATIONS_DIR).apply_pending()
    with test_db.get_connection(autocommit=True) as conn:
        names = tables_in(conn)
    assert names == LEAD_CORE_TABLES
    assert not names & FOREIGN_TABLES
