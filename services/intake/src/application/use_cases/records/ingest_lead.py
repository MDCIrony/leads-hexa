from typing import Optional

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
        tenant_id, record_id = existing_record.tenant_id.value, existing_record.id.value
        # Re-read, not trusted: the record in hand may be stale, and asking
        # lead-core about one that is already closed would create a lead that
        # nothing points back to.
        with self.uow:
            record = self.uow.intake_records.get_by_id_and_tenant(record_id, tenant_id)
        if record is None:
            raise DomainException("The intake record does not exist", error_code="INTAKE_RECORD_NOT_FOUND")
        if record.status == IntakeRecordStatus.PROMOTED:
            return self._already_promoted(record)
        if record.status not in _OPEN_STATUSES:
            raise self._not_open(record)
        # Organization and source come from the persisted record, never from the payload.
        request = AdmissionRequest(
            tenant_id=tenant_id,
            intake_record_id=record_id,
            source_id=record.source_id.value,
            candidate=candidate_of(command),
        )
        # No unit of work is open during the call: a connection held while
        # lead-core scores and routes would starve the pool. lead-core's
        # idempotency on (tenant, record) is what makes a repeat safe.
        admitted = self.admission.admit(request)
        self._ensure_decision(admitted)

        with self.uow:
            # Claimed rather than trusted: another run may have closed the
            # record while lead-core was deciding. Only an open record is
            # claimed; a discard that lands after the pre-read check but
            # before this claim is caught here.
            # Residual window: a discard landing during the admit call itself
            # cannot be undone, so lead-core keeps a lead this record never
            # points to. Closing it would need a compensating call to lead-core.
            claimed = self.uow.intake_records.claim_unpromoted(record_id, tenant_id)
            if claimed is None:
                # Read inside this same transaction: a second one would nest the unit of work.
                current = self.uow.intake_records.get_by_id_and_tenant(record_id, tenant_id)
                if current is not None and current.status == IntakeRecordStatus.PROMOTED:
                    return self._already_promoted(current)
                raise self._not_open(current)
            if admitted.outcome == "ADMITTED":
                claimed.promote(admitted.lead_id)
                self.uow.intake_records.save(claimed)
                return self._admitted(claimed, admitted)
            return self._rejected(claimed, admitted)

    @staticmethod
    def _ensure_decision(admitted: AdmissionResult) -> None:
        """Anything but a complete decision is an invalid body, hence transient."""
        if admitted.outcome == "ADMITTED" and not admitted.lead_id:
            raise AdmissionUnavailable("lead-core admitted the record without a lead_id")
        if admitted.outcome == "REJECTED" and not admitted.errors:
            raise AdmissionUnavailable("lead-core rejected the record without errors")
        if admitted.outcome not in ("ADMITTED", "REJECTED"):
            raise AdmissionUnavailable(f"lead-core answered an unknown outcome: {admitted.outcome}")

    @staticmethod
    def _not_open(record: Optional[IntakeRecord]) -> DomainException:
        status = record.status.value if record is not None else "missing"
        return DomainException(
            f"Cannot ingest an intake record from status {status}", error_code="INVALID_INTAKE_TRANSITION",
        )

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
