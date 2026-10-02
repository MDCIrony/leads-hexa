"""IngestLeadUseCase as intake will run it: claim and close the record, the decision behind LeadAdmissionPort."""
import uuid
from decimal import Decimal

import pytest

from application.dtos.admissions import AdmissionError, AdmissionResult
from application.dtos.commands import IngestLeadCommand
from application.ports.output.intake.lead_admission_port import AdmissionUnavailable, LeadAdmissionPort
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.intake.payloads import candidate_of, payload_of
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_LEAD_ID = str(uuid.uuid4())


class _FakeAdmission(LeadAdmissionPort):
    def __init__(self, result=None, error=None) -> None:
        self.result, self.error, self.requests = result, error, []

    def admit(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def _admitted() -> AdmissionResult:
    return AdmissionResult(outcome="ADMITTED", lead_id=_LEAD_ID, status="ASSIGNED", score=40,
                           assigned_agent_id=str(uuid.uuid4()), applied_rules_count=2)


def _command(**overrides) -> IngestLeadCommand:
    fields = dict(tenant_id=uuid.uuid4(), source_id=uuid.uuid4(), first_name="Jane", last_name="Doe",
                  company="Acme", budget=5000.5, industry="Tech", email="jane@example.com")
    fields.update(overrides)
    return IngestLeadCommand(**fields)


def _stored(uow, command, **fields) -> IntakeRecord:
    return uow.intake_records.save(IntakeRecord.create(
        tenant_id=command.tenant_id, source_id=command.source_id, payload=payload_of(command), **fields))


def test_an_admitted_candidate_promotes_the_record_with_lead_cores_answer():
    uow, command = InMemoryUnitOfWork(), _command()
    record = _stored(uow, command)
    admission = _FakeAdmission(_admitted())

    result = IngestLeadUseCase(uow, admission).execute(command, existing_record=record)

    sent = admission.requests[0]
    assert (sent.tenant_id, sent.intake_record_id, sent.source_id) == (
        command.tenant_id, record.id.value, command.source_id)
    assert (result.lead_id, result.status, result.score, result.applied_rules_count) == (_LEAD_ID, "ASSIGNED", 40, 2)
    stored = uow.intake_records.get_by_id_and_tenant(record.id.value, command.tenant_id)
    assert (stored.status, str(stored.lead_id)) == (IntakeRecordStatus.PROMOTED, _LEAD_ID)
    assert uow.outbox._entries == {}


def test_a_rejected_candidate_rejects_the_record_and_records_intake_rejected():
    uow, command = InMemoryUnitOfWork(), _command()
    record = _stored(uow, command)
    rejected = AdmissionResult(outcome="REJECTED", errors=(
        AdmissionError(field="email", message="bad email", error_code="INVALID_EMAIL"),))

    result = IngestLeadUseCase(uow, _FakeAdmission(rejected)).execute(command, existing_record=record)

    assert (result.status, result.error, result.error_code) == ("REJECTED", "bad email", "INVALID_EMAIL")
    stored = uow.intake_records.get_by_id_and_tenant(record.id.value, command.tenant_id)
    assert stored.status == IntakeRecordStatus.REJECTED
    assert [(e.field, e.error_code) for e in stored.errors] == [("email", "INVALID_EMAIL")]
    internal = uow.outbox.list_unpublished("internal", 10)
    assert [(e.event_type, e.payload["reason"]) for e in internal] == [("IntakeRejected", "bad email")]


def test_an_unavailable_admission_leaves_the_record_pending():
    uow, command = InMemoryUnitOfWork(), _command()
    record = _stored(uow, command)

    with pytest.raises(AdmissionUnavailable):
        IngestLeadUseCase(uow, _FakeAdmission(error=AdmissionUnavailable("down"))).execute(
            command, existing_record=record)

    assert uow.intake_records.get_by_id_and_tenant(record.id.value, command.tenant_id).status == (
        IntakeRecordStatus.PENDING)
    assert uow.outbox._entries == {}


def test_a_record_already_promoted_answers_its_lead_without_calling():
    uow, command = InMemoryUnitOfWork(), _command()
    record = _stored(uow, command, status=IntakeRecordStatus.PROMOTED, lead_id=_LEAD_ID)
    admission = _FakeAdmission(_admitted())

    result = IngestLeadUseCase(uow, admission).execute(command, existing_record=record)

    assert admission.requests == []
    assert (result.lead_id, result.status) == (_LEAD_ID, "PROMOTED")


def test_a_discarded_record_is_refused_before_lead_core_is_asked():
    uow, command = InMemoryUnitOfWork(), _command()
    record = _stored(uow, command, status=IntakeRecordStatus.DISCARDED)
    admission = _FakeAdmission(_admitted())

    with pytest.raises(Exception, match="DISCARDED"):
        IngestLeadUseCase(uow, admission).execute(command, existing_record=record)

    assert admission.requests == []


def test_the_candidate_travels_as_text():
    candidate = candidate_of(_command(budget=0.1, first_name=7, phone=None, custom_attributes={"a": 1}))

    assert (candidate.budget, candidate.first_name, candidate.phone) == ("0.1", "7", None)
    assert candidate_of(_command(budget=Decimal("9000.00"))).budget == "9000.00"
    assert candidate_of(_command(budget="12")).budget == "12"
    assert candidate.custom_attributes == {"a": 1}
