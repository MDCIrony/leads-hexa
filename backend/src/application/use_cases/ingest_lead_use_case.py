"""Intake's half of an ingestion: claim the record, ask lead-core, close the record.

The decision itself is AdmitLeadUseCase's, reached through LeadAdmissionPort:
in process before the cut, over HTTP after it. The flow is already the
post-cut one, so its behaviour without a single transaction is proven
before any table moves."""
from uuid import UUID

from application.dtos.admissions import AdmissionRequest, AdmissionResult
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.intake.lead_admission_port import LeadAdmissionPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.intake.payloads import candidate_of
from domain.entities.intake_record import IntakeError, IntakeRecord
from domain.events.intake_events import IntakeRejected
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeRecordStatus, LeadSourceKind


class IngestLeadUseCase(IngestLeadInputPort):
    def __init__(self, uow: UnitOfWorkPort, admission: LeadAdmissionPort) -> None:
        self.uow = uow
        self.admission = admission

    def resolve_source_id(self, tenant_id: UUID, kind: LeadSourceKind) -> UUID:
        """Looks up the tenant's active source for this channel. Every tenant
        gets a MANUAL_FORM and a FILE_UPLOAD source when it is provisioned
        (ProvisionTenantSourcesUseCase), so a miss here means the catalog is missing an
        entry, not that the caller sent a bad request."""
        with self.uow:
            source = self.uow.sources.get_by_kind(tenant_id, kind)
        if source is None:
            raise DomainException(
                f"No active source of kind {kind.value} found for this organization",
                error_code="SOURCE_NOT_FOUND",
            )
        return source.id.value

    def execute(self, command: IngestLeadCommand, existing_record: IntakeRecord) -> LeadProcessedResult:
        record_id, tenant_id = existing_record.id.value, command.tenant_id
        with self.uow:
            current = self.uow.intake_records.get_by_id_and_tenant(record_id, tenant_id)
        if current is None or current.status == IntakeRecordStatus.PROMOTED:
            return _already_promoted(current or existing_record)
        if current.status == IntakeRecordStatus.DISCARDED:
            # Refused before asking: once lead-core admits, a lead exists that
            # no record would point to.
            raise _not_promotable(current)

        # No transaction is open across this call: after the cut it is an HTTP
        # round trip, and the record's lock would be held for all of it. Two
        # runs racing here get the same lead, since admission is idempotent.
        result = self.admission.admit(AdmissionRequest(
            tenant_id=tenant_id, intake_record_id=record_id, source_id=command.source_id,
            candidate=candidate_of(command),
        ))

        with self.uow:
            # Claimed rather than trusted: the loser of a race between two runs
            # over the same job finds out here, and answers with the winner.
            record = self.uow.intake_records.claim_unpromoted(record_id, tenant_id)
            if record is None:
                latest = self.uow.intake_records.get_by_id_and_tenant(record_id, tenant_id) or current
                if latest.status != IntakeRecordStatus.PROMOTED:
                    raise _not_promotable(latest)
                return _already_promoted(latest)
            if result.outcome == "ADMITTED":
                record.promote(UUID(result.lead_id))
                self.uow.intake_records.save(record)
                return _promoted(record, result)
            errors = [IntakeError(field=e.field, message=e.message, error_code=e.error_code) for e in result.errors]
            record.reject(errors)
            self.uow.intake_records.save(record)
            self.uow.outbox.record(IntakeRejected(
                tenant_id=str(record.tenant_id.value), intake_record_id=str(record.id), reason=errors[0].message,
            ), channel="internal")
            return LeadProcessedResult(
                lead_id="", intake_record_id=str(record.id), status=IntakeRecordStatus.REJECTED.value,
                score=0, error=errors[0].message, error_code=errors[0].error_code,
            )


def _not_promotable(record: IntakeRecord) -> DomainException:
    return DomainException(
        f"Cannot promote an intake record from status {record.status.value}",
        error_code="INVALID_INTAKE_TRANSITION",
    )


def _promoted(record: IntakeRecord, result: AdmissionResult) -> LeadProcessedResult:
    return LeadProcessedResult(
        lead_id=result.lead_id or "", intake_record_id=str(record.id), status=result.status or "",
        score=result.score, assigned_agent_id=result.assigned_agent_id,
        applied_rules_count=result.applied_rules_count,
    )


def _already_promoted(record: IntakeRecord) -> LeadProcessedResult:
    """Another run got here first. Report its lead, publish nothing.

    Returning the winner's identifier rather than an error is what keeps a
    redelivered message idempotent: the caller sees the same answer it
    would have got had it won the race."""
    return LeadProcessedResult(
        lead_id=str(record.lead_id.value) if record.lead_id else "",
        intake_record_id=str(record.id),
        status=IntakeRecordStatus.PROMOTED.value,
        score=0,
    )
