from datetime import datetime, timedelta, timezone
from uuid import uuid4

from chassis.web import request_id_var

from domain.jobs.intake_job import IntakeJob
from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus
from infrastructure.adapters.output.persistence.intake_job_repository import PostgresIntakeJobRepository
from infrastructure.adapters.output.persistence.intake_record_repository import PostgresIntakeRecordRepository
from tests.integration.persistence.helpers import seed_source


def _job(source, kind=IntakeJobKind.SINGLE, created_at=None) -> IntakeJob:
    job = IntakeJob.create(tenant_id=source.tenant_id.value, source_id=source.id.value, kind=kind)
    if created_at:
        job.created_at = created_at
    return job


def test_a_new_job_survives_every_field(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    job = repo.save(_job(source))

    found = repo.get_by_id_and_tenant(job.id.value, source.tenant_id.value)

    assert (found.source_id.value, found.kind, found.status) == (source.id.value, IntakeJobKind.SINGLE, IntakeJobStatus.PENDING)
    assert (found.total_items, found.succeeded, found.failed) == (None, 0, 0)


def test_saving_twice_updates_instead_of_duplicating(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    job = repo.save(_job(source, IntakeJobKind.BATCH))
    job.start()
    job.set_total(5)
    job.set_counters(succeeded=1, failed=0)
    job.complete()
    repo.save(job)

    found = repo.get_by_id_and_tenant(job.id.value, source.tenant_id.value)

    assert (found.status, found.total_items, found.succeeded) == (IntakeJobStatus.COMPLETED, 5, 1)
    assert found.completed_at is not None
    assert repo.count_by_tenant(source.tenant_id.value) == 1


def test_list_and_count_filter_by_status_and_tenant(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    other = seed_source(conn)
    repo.save(_job(source))
    processing = _job(source)
    processing.start()
    repo.save(processing)
    repo.save(_job(other))
    tenant_id = source.tenant_id.value

    found = repo.list_by_tenant(tenant_id, status=IntakeJobStatus.PROCESSING)

    assert [j.id.value for j in found] == [processing.id.value]
    assert (repo.count_by_tenant(tenant_id), repo.count_by_tenant(tenant_id, IntakeJobStatus.PROCESSING)) == (2, 1)


def test_a_job_of_another_organization_reads_back_as_missing(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    job = repo.save(_job(source))

    assert repo.get_by_id_and_tenant(job.id.value, uuid4()) is None


def test_listing_orders_newest_first_and_pages(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    jobs = [repo.save(_job(source, created_at=base + timedelta(minutes=i))) for i in range(3)]

    found = repo.list_by_tenant(source.tenant_id.value, limit=3)
    paged = repo.list_by_tenant(source.tenant_id.value, limit=1, offset=1)

    assert [j.id.value for j in found] == [j.id.value for j in reversed(jobs)]
    assert [j.id.value for j in paged] == [jobs[1].id.value]


def test_count_by_source_counts_the_jobs_of_that_source_in_that_organization(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    repo.save(_job(source))
    repo.save(_job(source))
    repo.save(_job(seed_source(conn)))

    assert repo.count_by_source(source.tenant_id.value, source.id.value) == 2
    assert repo.count_by_source(uuid4(), source.id.value) == 0


def test_a_record_saved_with_a_job_id_reads_it_back(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    job = repo.save(_job(source))
    records = PostgresIntakeRecordRepository(conn)
    record = records.save(IntakeRecord.create(
        tenant_id=source.tenant_id.value, source_id=source.id.value, job_id=job.id.value, payload={"email": "a@x.test"}))

    found = records.get_by_id_and_tenant(record.id.value, source.tenant_id.value)

    assert found.job_id.value == job.id.value


def test_the_correlation_id_is_fixed_on_insert_and_survives_later_saves(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    job = _job(source)
    for request_id in ("rid-insert", "rid-worker"):
        reset = request_id_var.set(request_id)
        try:
            repo.save(job)
            job.start()
        finally:
            request_id_var.reset(reset)

    row = conn.execute("SELECT correlation_id FROM intake_jobs WHERE id = %s", (job.id.value,)).fetchone()

    assert row["correlation_id"] == "rid-insert"


def test_the_correlation_id_is_null_outside_a_request(conn):
    repo, source = PostgresIntakeJobRepository(conn), seed_source(conn)
    job = repo.save(_job(source))

    row = conn.execute("SELECT correlation_id FROM intake_jobs WHERE id = %s", (job.id.value,)).fetchone()

    assert row["correlation_id"] is None
