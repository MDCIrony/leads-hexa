from application.dtos.admissions import AdmissionRequest, AdmissionResult
from application.dtos.reception import IngestLeadCommand
from application.dtos.records import LeadProcessedResult
from application.ports.input.reception import IngestLeadInputPort
from application.ports.output.admissions import AdmissionUnavailable, LeadAdmissionPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.reception.payloads import candidate_of
from domain.events.intake_events import IntakeRejected
from domain.exceptions import DomainException
from domain.records.intake_record import IntakeError, IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus

_OPEN_STATUSES = (IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED)


class IngestLeadUseCase(IngestLeadInputPort):
    """Closes an intake record with lead-core's decision. The decision itself is not made here."""

    def __init__(self, uow: UnitOfWorkPort, admission: LeadAdmissionPort) -> None:
        self.uow = uow
        self.admission = admission

    def execute(self, command: IngestLeadCommand, existing_record: IntakeRecord) -> LeadProcessedResult:
        if existing_record.status == IntakeRecordStatus.PROMOTED:
            return self._already_promoted(existing_record)
        if existing_record.status not in _OPEN_STATUSES:
            # Refused before asking: lead-core would create a lead the record could not then point at.
            raise DomainException(
                f"Cannot ingest an intake record from status {existing_record.status.value}",
                error_code="INVALID_INTAKE_TRANSITION",
            )
        # Organization and source come from the persisted record, never from the payload.
        request = AdmissionRequest(
            tenant_id=existing_record.tenant_id.value,
            intake_record_id=existing_record.id.value,
            source_id=existing_record.source_id.value,
            candidate=candidate_of(command),
        )
        # No unit of work is open during the call: a connection held while
        # lead-core scores and routes would starve the pool. lead-core's
        # idempotency on (tenant, record) is what makes a repeat safe.
        admitted = self.admission.admit(request)
        if admitted.outcome == "ADMITTED" and not admitted.lead_id:
            raise AdmissionUnavailable("lead-core admitted the record without a lead_id")
        if admitted.outcome not in ("ADMITTED", "REJECTED"):
            raise AdmissionUnavailable(f"lead-core answered an unknown outcome: {admitted.outcome}")

        with self.uow:
            # Claimed rather than trusted: another run may have closed the
            # record while lead-core was deciding.
            record = self.uow.intake_records.claim_unpromoted(existing_record.id.value, request.tenant_id)
            if record is None:
                return self._already_promoted(
                    self.uow.intake_records.get_by_id_and_tenant(existing_record.id.value, request.tenant_id)
                    or existing_record
                )
            if admitted.outcome == "ADMITTED":
                record.promote(admitted.lead_id)
                self.uow.intake_records.save(record)
                return self._admitted(record, admitted)
            return self._rejected(record, admitted)

    def _rejected(self, record: IntakeRecord, admitted: AdmissionResult) -> LeadProcessedResult:
        errors = [IntakeError(field=e.field, message=e.message, error_code=e.error_code) for e in admitted.errors]
        record.reject(errors)
        self.uow.intake_records.save(record)
        self.uow.outbox.record(IntakeRejected(
            tenant_id=str(record.tenant_id.value),
            intake_record_id=str(record.id),
            reason=errors[0].message,
        ), channel="internal")
        return LeadProcessedResult(
            lead_id="",
            intake_record_id=str(record.id),
            status=IntakeRecordStatus.REJECTED.value,
            score=0,
            error=errors[0].message,
            error_code=errors[0].error_code,
        )

    @staticmethod
    def _admitted(record: IntakeRecord, admitted: AdmissionResult) -> LeadProcessedResult:
        return LeadProcessedResult(
            lead_id=str(record.lead_id),
            intake_record_id=str(record.id),
            status=admitted.status or "",
            score=admitted.score,
            assigned_agent_id=admitted.assigned_agent_id,
            applied_rules_count=admitted.applied_rules_count,
        )

    @staticmethod
    def _already_promoted(record: IntakeRecord) -> LeadProcessedResult:
        """Another run got here first: report its lead and publish nothing.

        Answering with the winner's identifier instead of an error keeps a
        redelivered message idempotent."""
        return LeadProcessedResult(
            lead_id=str(record.lead_id) if record.lead_id else "",
            intake_record_id=str(record.id),
            status=IntakeRecordStatus.PROMOTED.value,
            score=0,
        )
