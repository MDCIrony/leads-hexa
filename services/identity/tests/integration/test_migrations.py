from pathlib import Path

import psycopg
import pytest

from chassis.persistence import MigrationRunner

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_TABLES = {
    "tenants", "agents", "auth_sessions", "auth_challenges", "agent_mfa",
    "mfa_recovery_codes", "social_identities", "outbox_events",
}

_AGENT_COLUMNS = {
    "id": ("uuid", "NO"),
    "name": ("text", "NO"),
    "email": ("text", "NO"),
    "is_active": ("boolean", "NO"),
    "role": ("text", "NO"),
    "hashed_password": ("text", "YES"),
    "tenant_id": ("uuid", "YES"),
    "version": ("bigint", "NO"),
}

_INDEXES = {
    "tenants_slug_key", "idx_agents_tenant", "idx_agents_email_normalized",
    "idx_auth_sessions_expires_at", "idx_auth_challenges_expires_at", "idx_auth_challenges_oauth_token_hash",
    "social_identities_provider_subject_key", "social_identities_agent_provider_key",
    "idx_outbox_unpublished_by_channel", "idx_outbox_unpublished_by_key",
}

_CHECKS = {
    "auth_challenges_purpose_check", "auth_challenges_attempts_check", "auth_challenges_provider_check",
    "auth_challenges_oauth_data_check", "auth_challenges_mfa_oauth_data_check",
    "agent_mfa_secret_ciphertext_check", "mfa_recovery_codes_code_hash_check",
    "social_identities_provider_check", "social_identities_provider_subject_check",
    "social_identities_email_at_link_check", "outbox_events_channel_check",
}


def _rows(database, query, params=()):
    with database.get_connection(autocommit=True) as conn:
        return conn.execute(query, params).fetchall()


def test_every_file_can_run_twice_over_the_finished_schema(test_db):
    # Straight through, not via the runner: the runner would skip what it has
    # recorded, and the point is that the SQL itself is safe to repeat.
    for _ in range(2):
        for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            with test_db.get_connection(autocommit=True) as conn:
                conn.execute(path.read_text(encoding="utf-8"))

    assert MigrationRunner(test_db, _MIGRATIONS_DIR).apply_pending() == []


def test_creates_exactly_the_identity_tables(test_db):
    rows = _rows(test_db, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    assert {row["tablename"] for row in rows} == _TABLES | {"schema_migrations"}


def test_agents_has_the_final_columns_and_no_group(test_db):
    rows = _rows(
        test_db,
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s",
        ("agents",),
    )
    assert {row["column_name"]: (row["data_type"], row["is_nullable"]) for row in rows} == _AGENT_COLUMNS


def test_tenants_and_the_outbox_carry_the_columns_projections_and_the_relay_need(test_db):
    rows = _rows(
        test_db,
        "SELECT table_name, column_name, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name IN ('tenants', 'outbox_events')",
    )
    columns = {(row["table_name"], row["column_name"]): row["is_nullable"] for row in rows}
    assert columns[("tenants", "version")] == "NO"
    assert columns[("outbox_events", "channel")] == "NO"
    assert columns[("outbox_events", "tenant_id")] == "YES"
    assert ("outbox_events", "correlation_id") in columns


def test_creates_the_indexes_and_checks(test_db):
    indexes = _rows(test_db, "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    checks = _rows(test_db, "SELECT conname FROM pg_constraint WHERE contype = 'c'")
    assert _INDEXES <= {row["indexname"] for row in indexes}
    assert _CHECKS <= {row["conname"] for row in checks}


def test_no_foreign_key_leaves_the_identity_schema(test_db):
    rows = _rows(
        test_db,
        "SELECT confrelid::regclass::text AS target FROM pg_constraint WHERE contype = 'f'",
    )
    assert {row["target"] for row in rows} <= _TABLES


def test_emails_are_unique_once_normalized(test_db):
    insert = "INSERT INTO agents (id, name, email) VALUES (gen_random_uuid(), 'A', %s)"
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(insert, ("ana@acme.test",))
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(insert, ("ANA@acme.test",))
