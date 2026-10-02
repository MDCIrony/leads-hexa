"""Migration 018: leads remember their intake record, once, and no longer point at lead_sources."""
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

_MIGRATION = (Path(__file__).resolve().parents[3] / "migrations" / "018_intake_record_link.sql").read_text(
    encoding="utf-8")


def _lead(conn, tenant, source, lead_id=None, intake_record_id=None):
    lead_id = lead_id or uuid4()
    conn.execute(
        "INSERT INTO leads (id, tenant_id, source_id, first_name, last_name, company, budget, industry,"
        " status, intake_record_id, created_at) VALUES (%s, %s, %s, 'A', 'B', 'C', 10, 'D', 'NEW', %s, now())",
        (lead_id, tenant, source, intake_record_id),
    )
    return lead_id


def test_it_runs_twice_and_backfills_the_link_from_promoted_records(test_db):
    tenant, source, record = uuid4(), uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute("INSERT INTO lead_sources (id, tenant_id, name, kind, created_at, updated_at)"
                     " VALUES (%s, %s, 'F', 'MANUAL_FORM', now(), now())",
                     (source, tenant))
        lead_id = _lead(conn, tenant, source)
        conn.execute(
            "INSERT INTO intake_records (id, tenant_id, source_id, payload, status, lead_id, received_at)"
            " VALUES (%s, %s, %s, '{}', 'PROMOTED', %s, now())", (record, tenant, source, lead_id))

        conn.execute(_MIGRATION)
        conn.execute(_MIGRATION)

        row = conn.execute("SELECT intake_record_id FROM leads WHERE id = %s", (lead_id,)).fetchone()
        assert row["intake_record_id"] == record


def test_one_intake_record_admits_one_lead_per_organization(test_db):
    tenant, record = uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        _lead(conn, tenant, uuid4(), intake_record_id=record)
        _lead(conn, tenant, uuid4())
        _lead(conn, tenant, uuid4())

        with pytest.raises(psycopg.errors.UniqueViolation) as raised:
            _lead(conn, tenant, uuid4(), intake_record_id=record)

        assert raised.value.diag.constraint_name == "uq_leads_tenant_intake_record"


def test_a_lead_may_name_a_source_born_outside_this_database(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        _lead(conn, uuid4(), uuid4())

        row = conn.execute(
            "SELECT COUNT(*) AS count FROM pg_constraint"
            " WHERE contype = 'f' AND conrelid = 'leads'::regclass AND confrelid = 'lead_sources'::regclass"
        ).fetchone()
        assert row["count"] == 0
