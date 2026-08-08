from uuid import uuid4

import psycopg

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
        job.record_success()
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
