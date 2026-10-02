from uuid import uuid4

from domain.entities.intake_job import IntakeJob
from domain.entities.lead_source import LeadSource
from domain.entities.tenant import Tenant
from domain.value_objects.enums import IntakeJobKind, LeadSourceKind
from infrastructure.adapters.output.persistence.raw_sql_intake_file_repository import (
    RawSqlIntakeFileRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_intake_job_repository import (
    RawSqlIntakeJobRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)


def _seed_job(conn):
    # intake_files.job_id is a foreign key to intake_jobs, which in turn needs
    # a persisted tenant and source.
    tenant = RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))
    source = RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant.id.value, name="Fuente", kind=LeadSourceKind.MANUAL_FORM)
    )
    job = RawSqlIntakeJobRepository(conn).save(
        IntakeJob.create(tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.BATCH)
    )
    return job


def _ctx(test_db):
    ctx = test_db.get_connection(autocommit=True)
    return ctx.__enter__(), ctx


def test_save_and_get_round_trip_the_bytes(test_db):
    conn, ctx = _ctx(test_db)
    try:
        job = _seed_job(conn)
        repo = RawSqlIntakeFileRepository(conn)
        content = b"first_name,email\r\nAna,ana@x.test\n\x00\xff"

        repo.save(job.id.value, job.tenant_id.value, "leads.csv", content)
        stored = repo.get(job.id.value, job.tenant_id.value)

        assert stored is not None
        assert stored.job_id == job.id.value
        assert stored.tenant_id == job.tenant_id.value
        assert stored.filename == "leads.csv"
        assert stored.content == content
        assert stored.parsed_at is None
    finally:
        ctx.__exit__(None, None, None)


def test_another_tenant_cannot_read_the_file(test_db):
    conn, ctx = _ctx(test_db)
    try:
        job = _seed_job(conn)
        repo = RawSqlIntakeFileRepository(conn)
        repo.save(job.id.value, job.tenant_id.value, "leads.csv", b"x")

        assert repo.get(job.id.value, uuid4()) is None
        assert repo.get(uuid4(), job.tenant_id.value) is None
    finally:
        ctx.__exit__(None, None, None)


def test_mark_parsed_stamps_the_file(test_db):
    conn, ctx = _ctx(test_db)
    try:
        job = _seed_job(conn)
        repo = RawSqlIntakeFileRepository(conn)
        repo.save(job.id.value, job.tenant_id.value, "leads.csv", b"x")

        repo.mark_parsed(job.id.value)

        assert repo.get(job.id.value, job.tenant_id.value).parsed_at is not None
    finally:
        ctx.__exit__(None, None, None)


def test_a_second_reader_waits_for_the_first_parse_and_then_sees_it_done(test_db):
    """Two consumers of the same job: the second cannot read the file while the
    first holds it, so it can never parse it a second time."""
    import psycopg
    import pytest

    seed, seed_ctx = _ctx(test_db)
    try:
        job = _seed_job(seed)
        RawSqlIntakeFileRepository(seed).save(job.id.value, job.tenant_id.value, "leads.csv", b"x")
    finally:
        seed_ctx.__exit__(None, None, None)

    first_ctx, second_ctx = test_db.get_connection(), test_db.get_connection()
    first, second = first_ctx.__enter__(), second_ctx.__enter__()
    try:
        assert RawSqlIntakeFileRepository(first).get(job.id.value, job.tenant_id.value).parsed_at is None

        second.execute("SET lock_timeout = '200ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            RawSqlIntakeFileRepository(second).get(job.id.value, job.tenant_id.value)
        second.rollback()

        RawSqlIntakeFileRepository(first).mark_parsed(job.id.value)
        first.commit()

        assert RawSqlIntakeFileRepository(second).get(job.id.value, job.tenant_id.value).parsed_at is not None
        second.commit()
    finally:
        first_ctx.__exit__(None, None, None)
        second_ctx.__exit__(None, None, None)
