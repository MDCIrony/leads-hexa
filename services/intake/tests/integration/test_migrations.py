from pathlib import Path

import psycopg
import pytest

from chassis.persistence import MigrationRunner

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_TABLES = {
    "lead_sources", "provisioned_tenants", "intake_jobs", "intake_records", "intake_errors",
    "intake_files", "outbox_events", "processed_events",
}

# Only what stays inside intake_db: records/jobs -> sources, records -> jobs, errors -> records, files -> jobs.
_FOREIGN_KEYS = {
    ("intake_jobs", "lead_sources"), ("intake_records", "lead_sources"), ("intake_records", "intake_jobs"),
    ("intake_errors", "intake_records"), ("intake_files", "intake_jobs"),
}

_INDEXES = {
    "lead_sources_tenant_id_name_key", "idx_lead_sources_tenant", "idx_intake_records_inbox",
    "idx_intake_records_job", "idx_intake_errors_record", "idx_intake_jobs_tenant_status",
    "idx_outbox_unpublished_by_channel", "idx_outbox_unpublished_by_key",
}

_NULLABLE = {
    ("outbox_events", "tenant_id"): "YES",
    ("outbox_events", "channel"): "NO",
    ("outbox_events", "correlation_id"): "YES",
    ("intake_jobs", "correlation_id"): "YES",
    ("intake_records", "lead_id"): "YES",
    ("intake_records", "job_id"): "YES",
    ("lead_sources", "tenant_id"): "NO",
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


def test_creates_exactly_the_intake_tables(test_db):
    rows = _rows(test_db, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    assert {row["tablename"] for row in rows} == _TABLES | {"schema_migrations"}


def test_the_only_foreign_keys_are_the_ones_inside_intake_db(test_db):
    # Tenants live in identity_db and leads in leads_db: tenant_id and lead_id are external ids.
    rows = _rows(
        test_db,
        "SELECT conrelid::regclass::text AS source, confrelid::regclass::text AS target "
        "FROM pg_constraint WHERE contype = 'f'",
    )
    assert {(row["source"], row["target"]) for row in rows} == _FOREIGN_KEYS


def test_creates_the_indexes(test_db):
    rows = _rows(test_db, "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    assert _INDEXES <= {row["indexname"] for row in rows}


def test_nullability_is_as_expected_for_the_columns_that_changed(test_db):
    rows = _rows(
        test_db,
        "SELECT table_name, column_name, is_nullable FROM information_schema.columns WHERE table_schema = 'public'",
    )
    columns = {(row["table_name"], row["column_name"]): row["is_nullable"] for row in rows}
    assert {key: columns[key] for key in _NULLABLE} == _NULLABLE


def test_the_outbox_accepts_only_the_internal_and_job_channels(test_db):
    insert = (
        "INSERT INTO outbox_events (id, partition_key, event_type, payload, occurred_on, channel) "
        "VALUES (gen_random_uuid(), 'k', 'E', '{}', now(), %s)"
    )
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(insert, ("job",))
        conn.execute(insert, ("internal",))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(insert, ("product",))


def test_a_source_name_is_unique_per_organization(test_db):
    insert = (
        "INSERT INTO lead_sources (id, tenant_id, name, kind, created_at, updated_at) "
        "VALUES (gen_random_uuid(), %s, 'Form', 'MANUAL_FORM', now(), now())"
    )
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(insert, ("11111111-1111-1111-1111-111111111111",))
        conn.execute(insert, ("22222222-2222-2222-2222-222222222222",))
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(insert, ("11111111-1111-1111-1111-111111111111",))
