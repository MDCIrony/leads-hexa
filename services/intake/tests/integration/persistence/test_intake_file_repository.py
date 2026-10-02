from uuid import uuid4

import psycopg
import pytest

from infrastructure.adapters.output.persistence.intake_file_repository import PostgresIntakeFileRepository
from tests.integration.persistence.helpers import seed_job, seed_source


def _seed(conn):
    job = seed_job(conn, seed_source(conn))
    return PostgresIntakeFileRepository(conn), job


def test_the_bytes_round_trip(conn):
    repo, job = _seed(conn)
    content = b"first_name,email\r\nAna,ana@x.test\n\x00\xff"

    repo.save(job.id.value, job.tenant_id.value, "leads.csv", content)
    stored = repo.get(job.id.value, job.tenant_id.value)

    assert (stored.job_id, stored.tenant_id, stored.filename) == (job.id.value, job.tenant_id.value, "leads.csv")
    assert (stored.content, stored.parsed_at) == (content, None)


def test_another_organization_cannot_read_the_file(conn):
    repo, job = _seed(conn)
    repo.save(job.id.value, job.tenant_id.value, "leads.csv", b"x")

    assert repo.get(job.id.value, uuid4()) is None
    assert repo.get(uuid4(), job.tenant_id.value) is None


def test_mark_parsed_stamps_the_file(conn):
    repo, job = _seed(conn)
    repo.save(job.id.value, job.tenant_id.value, "leads.csv", b"x")

    repo.mark_parsed(job.id.value)

    assert repo.get(job.id.value, job.tenant_id.value).parsed_at is not None


def test_a_second_reader_waits_for_the_first_parse_and_then_sees_it_done(test_db, conn):
    """Two consumers of one job: the second cannot read the file while the first holds
    it, so it can never parse it a second time."""
    repo, job = _seed(conn)
    repo.save(job.id.value, job.tenant_id.value, "leads.csv", b"x")

    with test_db.get_connection() as first, test_db.get_connection() as second:
        assert PostgresIntakeFileRepository(first).get(job.id.value, job.tenant_id.value).parsed_at is None

        second.execute("SET lock_timeout = '200ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            PostgresIntakeFileRepository(second).get(job.id.value, job.tenant_id.value)
        second.rollback()

        PostgresIntakeFileRepository(first).mark_parsed(job.id.value)
        first.commit()

        assert PostgresIntakeFileRepository(second).get(job.id.value, job.tenant_id.value).parsed_at is not None
        second.commit()
