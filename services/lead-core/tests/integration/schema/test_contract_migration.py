"""Migration 019: leads_db keeps only lead-core's tables, and the whole chain can run again."""
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from chassis.persistence import MigrationRunner, RawSqlDatabase
from psycopg import sql
from psycopg.conninfo import make_conninfo

from tests.integration.schema.tables import FOREIGN_TABLES, LEAD_CORE_TABLES, foreign_key_targets, tables_in

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
_CONTRACT = (_MIGRATIONS_DIR / "019_drop_foreign_tables.sql").read_text(encoding="utf-8")


def _lead(conn, tenant, source, intake_record_id=None):
    lead_id = uuid4()
    conn.execute(
        "INSERT INTO leads (id, tenant_id, source_id, first_name, last_name, company, budget, industry,"
        " status, intake_record_id, created_at) VALUES (%s, %s, %s, 'A', 'B', 'C', 10, 'D', 'NEW', %s, now())",
        (lead_id, tenant, source, intake_record_id),
    )
    return lead_id


def _lead_foreign_keys(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS count FROM pg_constraint WHERE contype = 'f' AND conrelid = 'leads'::regclass"
    ).fetchone()["count"]


def test_leads_db_holds_only_lead_core_tables_and_no_key_points_outside_them(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        assert tables_in(conn) == LEAD_CORE_TABLES
        assert foreign_key_targets(conn) <= LEAD_CORE_TABLES


def test_the_contract_migration_runs_twice_in_a_row(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(_CONTRACT)
        conn.execute(_CONTRACT)
        assert tables_in(conn) == LEAD_CORE_TABLES


def test_one_intake_record_admits_one_lead_per_organization(test_db):
    tenant, record = uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        _lead(conn, tenant, uuid4(), intake_record_id=record)
        _lead(conn, tenant, uuid4())
        _lead(conn, tenant, uuid4())

        with pytest.raises(psycopg.errors.UniqueViolation) as raised:
            _lead(conn, tenant, uuid4(), intake_record_id=record)

        assert raised.value.diag.constraint_name == "uq_leads_tenant_intake_record"


def test_the_chain_reapplies_over_leads_of_tenants_and_sources_born_elsewhere(test_db, dsn_of_test_db):
    schema = f"f5_{uuid4().hex}"
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    database = RawSqlDatabase(make_conninfo(dsn_of_test_db, options=f"-c search_path={schema}"))
    runner = MigrationRunner(database, _MIGRATIONS_DIR)
    try:
        runner.apply_pending()
        with database.get_connection(autocommit=True) as conn:
            assert tables_in(conn, schema) == LEAD_CORE_TABLES
            # Neither the tenant nor the source exists anywhere, as after the identity and intake cuts.
            lead_id = _lead(conn, uuid4(), uuid4())
            conn.execute("DELETE FROM schema_migrations")

        reapplied = runner.apply_pending()

        assert reapplied == sorted(path.name for path in _MIGRATIONS_DIR.glob("*.sql"))
        with database.get_connection(autocommit=True) as conn:
            assert conn.execute("SELECT id FROM leads").fetchall() == [{"id": lead_id}]
            assert not tables_in(conn, schema) & FOREIGN_TABLES
            assert _lead_foreign_keys(conn) == 0
    finally:
        database.close()
        with test_db.get_connection(autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
