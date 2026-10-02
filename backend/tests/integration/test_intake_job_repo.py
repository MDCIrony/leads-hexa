from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg

from chassis.web import request_id_var

from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from domain.entities.lead_source import LeadSource
from domain.entities.tenant import Tenant
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus, LeadSourceKind
from infrastructure.adapters.output.persistence.raw_sql_intake_job_repository import (
    RawSqlIntakeJobRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_intake_record_repository import (
    RawSqlIntakeRecordRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlIntakeJobRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> Tenant:
    # A real row is required: intake_jobs.tenant_id has a foreign key to tenants.
    return RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))


def _source(conn: psycopg.Connection, tenant_id) -> LeadSource:
    # Same reason as _tenant: intake_jobs.source_id has a foreign key to lead_sources.
    return RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant_id, name=f"Fuente {uuid4()}", kind=LeadSourceKind.MANUAL_FORM)
    )


def test_saving_and_retrieving_a_job_survives_every_field(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        job = IntakeJob.create(
            tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE
        )

        repo.save(job)

        found = repo.get_by_id_and_tenant(job.id.value, tenant.id.value)
        assert found is not None
        assert found.tenant_id.value == tenant.id.value
        assert found.source_id.value == source.id.value
        assert found.kind == IntakeJobKind.SINGLE
        assert found.status == IntakeJobStatus.PENDING
        assert found.total_items is None
        assert found.succeeded == 0
        assert found.failed == 0
    finally:
        ctx.__exit__(None, None, None)


def test_saving_twice_updates_instead_of_duplicating(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        job = IntakeJob.create(
            tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.BATCH
        )
        repo.save(job)

        job.start()
        job.set_total(5)
        job.set_counters(succeeded=1, failed=0)
        job.complete()
        repo.save(job)

        found = repo.get_by_id_and_tenant(job.id.value, tenant.id.value)
        assert found is not None
        assert found.status == IntakeJobStatus.COMPLETED
        assert found.total_items == 5
        assert found.succeeded == 1
        assert found.completed_at is not None
        assert repo.count_by_tenant(tenant.id.value) == 1
    finally:
        ctx.__exit__(None, None, None)


def test_list_by_tenant_filters_by_status(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        pending = IntakeJob.create(
            tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE
        )
        repo.save(pending)

        processing = IntakeJob.create(
            tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE
        )
        processing.start()
        repo.save(processing)

        found = repo.list_by_tenant(tenant.id.value, status=IntakeJobStatus.PROCESSING)

        assert [j.id.value for j in found] == [processing.id.value]
    finally:
        ctx.__exit__(None, None, None)


def test_get_by_id_and_tenant_from_another_organization_is_none(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        other_tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        job = IntakeJob.create(
            tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE
        )
        repo.save(job)

        assert repo.get_by_id_and_tenant(job.id.value, other_tenant.id.value) is None
    finally:
        ctx.__exit__(None, None, None)


def test_an_intake_record_saved_with_a_job_id_reads_it_back(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        job = IntakeJob.create(
            tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE
        )
        repo.save(job)

        record_repo = RawSqlIntakeRecordRepository(conn)
        record = IntakeRecord.create(
            tenant_id=tenant.id.value,
            source_id=source.id.value,
            job_id=job.id.value,
            payload={"email": "lead@example.com"},
        )
        record_repo.save(record)

        found = record_repo.get_by_id_and_tenant(record.id.value, tenant.id.value)
        assert found is not None
        assert found.job_id is not None
        assert found.job_id.value == job.id.value
    finally:
        ctx.__exit__(None, None, None)


def test_list_by_tenant_orders_newest_first(test_db):
    """Explicit timestamps avoid flakiness on systems fast enough to save all
    three within the same microsecond."""
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)

        first = IntakeJob.create(tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE)
        first.created_at = base
        second = IntakeJob.create(tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE)
        second.created_at = base + timedelta(minutes=1)
        third = IntakeJob.create(tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE)
        third.created_at = base + timedelta(minutes=2)
        repo.save(first)
        repo.save(second)
        repo.save(third)

        found = repo.list_by_tenant(tenant.id.value, limit=3, offset=0)

        assert [j.id.value for j in found] == [third.id.value, second.id.value, first.id.value]
    finally:
        ctx.__exit__(None, None, None)


def test_correlation_id_is_fixed_on_insert_and_survives_later_saves(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        job = IntakeJob.create(
            tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE
        )

        token = request_id_var.set("rid-insert")
        try:
            repo.save(job)
        finally:
            request_id_var.reset(token)
        token = request_id_var.set("rid-worker")
        try:
            job.start()
            repo.save(job)
        finally:
            request_id_var.reset(token)

        row = conn.execute(
            "SELECT correlation_id FROM intake_jobs WHERE id = %s", (job.id.value,)
        ).fetchone()
        assert row["correlation_id"] == "rid-insert"
    finally:
        ctx.__exit__(None, None, None)


def test_correlation_id_is_null_outside_a_request(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        job = repo.save(
            IntakeJob.create(tenant_id=tenant.id.value, source_id=source.id.value, kind=IntakeJobKind.SINGLE)
        )

        row = conn.execute(
            "SELECT correlation_id FROM intake_jobs WHERE id = %s", (job.id.value,)
        ).fetchone()
        assert row["correlation_id"] is None
    finally:
        ctx.__exit__(None, None, None)
