from uuid import uuid4

import psycopg

from domain.entities.intake_record import IntakeError, IntakeRecord
from domain.entities.lead_source import LeadSource
from domain.entities.tenant import Tenant
from domain.value_objects.enums import IntakeRecordStatus, LeadSourceKind
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
    return RawSqlIntakeRecordRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> Tenant:
    # A real row is required: intake_records.tenant_id has a foreign key to
    # tenants (migration 005).
    return RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))


def _source(conn: psycopg.Connection, tenant_id) -> LeadSource:
    # Same reason as _tenant: intake_records.source_id has a foreign key to
    # lead_sources.
    return RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant_id, name=f"Fuente {uuid4()}", kind=LeadSourceKind.MANUAL_FORM)
    )


def test_saving_two_errors_reads_both_back(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        record = IntakeRecord.create(
            tenant_id=tenant.id.value,
            source_id=source.id.value,
            payload={"email": "not-an-email"},
        )
        record.reject(
            [
                IntakeError(field="email", message="Invalid format"),
                IntakeError(field="phone", message="Missing"),
            ]
        )

        repo.save(record)

        found = repo.get_by_id_and_tenant(record.id.value, tenant.id.value)
        assert found is not None
        assert found.status == IntakeRecordStatus.REJECTED
        assert {e.field for e in found.errors} == {"email", "phone"}
    finally:
        ctx.__exit__(None, None, None)


def test_saving_again_with_fewer_errors_replaces_the_previous_set(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        record = IntakeRecord.create(
            tenant_id=tenant.id.value,
            source_id=source.id.value,
            payload={"email": "not-an-email"},
        )
        record.reject(
            [
                IntakeError(field="email", message="Invalid format"),
                IntakeError(field="phone", message="Missing"),
            ]
        )
        repo.save(record)

        resaved = IntakeRecord.create(
            record_id=record.id.value,
            tenant_id=tenant.id.value,
            source_id=source.id.value,
            payload=record.payload,
            status=IntakeRecordStatus.REJECTED,
            errors=[IntakeError(field="email", message="Still invalid")],
        )
        repo.save(resaved)

        found = repo.get_by_id_and_tenant(record.id.value, tenant.id.value)
        assert found is not None
        assert len(found.errors) == 1
        assert found.errors[0].field == "email"
    finally:
        ctx.__exit__(None, None, None)
