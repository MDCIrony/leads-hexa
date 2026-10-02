from uuid import uuid4

import pytest

from domain.events.intake_events import IntakeRejected
from domain.exceptions import DomainException
from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork


def _source(tenant_id, name="Form") -> LeadSource:
    return LeadSource.create(tenant_id=tenant_id, name=name, kind=LeadSourceKind.MANUAL_FORM)


def _count(conn, query: str) -> int:
    return conn.execute(query).fetchone()["n"]


_SOURCES = "SELECT COUNT(*) AS n FROM lead_sources"
_OUTBOX = "SELECT COUNT(*) AS n FROM outbox_events"


def test_the_block_commits_on_success_and_can_be_entered_again(test_db, conn):
    uow, tenant_id = PostgresUnitOfWork(test_db), uuid4()

    with uow:
        uow.sources.save(_source(tenant_id, "One"))
    with uow:
        uow.sources.save(_source(tenant_id, "Two"))

    assert _count(conn, _SOURCES) == 2


def test_an_error_rolls_back_every_write_of_the_block_the_outbox_included(test_db, conn):
    uow, tenant_id = PostgresUnitOfWork(test_db), uuid4()

    with pytest.raises(RuntimeError):
        with uow:
            uow.sources.save(_source(tenant_id))
            uow.outbox.record(IntakeRejected(tenant_id=str(tenant_id), intake_record_id=str(uuid4()), reason="x"))
            raise RuntimeError("boom")

    assert (_count(conn, _SOURCES), _count(conn, _OUTBOX)) == (0, 0)


@pytest.mark.parametrize("statement, params, code", [
    ("INSERT INTO lead_sources (id, tenant_id, name, kind, created_at, updated_at) "
     "VALUES (%s, %s, 'Dup', 'MANUAL_FORM', now(), now())", "duplicate", "ALREADY_EXISTS"),
    ("INSERT INTO intake_jobs (id, tenant_id, source_id, kind, status, created_at) "
     "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 'SINGLE', 'PENDING', now())", None,
     "RELATED_ENTITY_NOT_FOUND"),
    ("INSERT INTO lead_sources (id, tenant_id, kind, created_at, updated_at) "
     "VALUES (gen_random_uuid(), gen_random_uuid(), 'MANUAL_FORM', now(), now())", None, "MISSING_REQUIRED_FIELD"),
], ids=["unique", "foreign-key", "not-null"])
def test_a_constraint_violation_becomes_a_domain_exception_and_returns_the_connection(test_db, statement, params, code):
    uow, tenant_id = PostgresUnitOfWork(test_db), uuid4()
    with uow:
        uow.sources.save(_source(tenant_id, "Dup"))

    with pytest.raises(DomainException) as caught:
        with uow:
            if params == "duplicate":
                uow.connection.execute(statement, (uuid4(), tenant_id))
            else:
                uow.connection.execute(statement)

    assert caught.value.error_code == code
    assert uow.connection is None
