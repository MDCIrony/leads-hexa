from uuid import UUID, uuid4

from domain.jobs.intake_job import IntakeJob
from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import IntakeJobKind, LeadSourceKind
from infrastructure.adapters.output.persistence.intake_job_repository import PostgresIntakeJobRepository
from infrastructure.adapters.output.persistence.lead_source_repository import PostgresLeadSourceRepository


def seed_source(conn, tenant_id: UUID | None = None, kind: LeadSourceKind = LeadSourceKind.MANUAL_FORM) -> LeadSource:
    # tenant_id is a plain UUID: organizations live in identity_db, so no row backs it.
    return PostgresLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant_id or uuid4(), name=f"Source {uuid4()}", kind=kind))


def seed_job(conn, source: LeadSource, kind: IntakeJobKind = IntakeJobKind.BATCH) -> IntakeJob:
    return PostgresIntakeJobRepository(conn).save(
        IntakeJob.create(tenant_id=source.tenant_id.value, source_id=source.id.value, kind=kind))
