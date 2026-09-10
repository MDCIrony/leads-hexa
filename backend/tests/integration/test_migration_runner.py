from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from infrastructure.adapters.output.persistence.migration_runner import MigrationRunner

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


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
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
    names = {row["table_name"] for row in rows}
    assert {
        "leads", "scoring_rules", "agents", "webhook_configs",
        "sales_groups", "assignment_rules",
    } <= names


def test_email_normalization_migration_rolls_back_historical_collisions(test_db):
    migration = (_MIGRATIONS_DIR / "011_normalize_agent_emails.sql").read_text(encoding="utf-8")
    first_id, second_id = uuid4(), uuid4()

    with test_db.get_connection(autocommit=True) as conn:
        conn.execute("DROP INDEX IF EXISTS idx_agents_email_normalized")
        conn.execute(
            "INSERT INTO agents (id, name, email, is_active, role, tenant_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (first_id, "First", " Legacy@Example.Test ", True, "AGENT", uuid4()),
        )
        conn.execute(
            "INSERT INTO agents (id, name, email, is_active, role, tenant_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (second_id, "Second", "legacy@example.test", True, "AGENT", uuid4()),
        )
        try:
            with pytest.raises(psycopg.errors.RaiseException, match="duplicate normalized email") as exc_info:
                conn.execute(migration)
            conn.execute("ROLLBACK")

            assert "legacy@example.test" in str(exc_info.value)
            emails = conn.execute(
                "SELECT email FROM agents WHERE id IN (%s, %s) ORDER BY id", (first_id, second_id)
            ).fetchall()
            assert {row["email"] for row in emails} == {" Legacy@Example.Test ", "legacy@example.test"}
            assert conn.execute("SELECT to_regclass('public.idx_agents_email_normalized') AS name").fetchone()["name"] is None
        finally:
            conn.execute("DELETE FROM agents WHERE id IN (%s, %s)", (first_id, second_id))
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_email_normalized ON agents (lower(email))")
