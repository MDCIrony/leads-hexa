"""The split ingestion: ask lead-core with no transaction open, then close the record in one."""
from uuid import UUID, uuid4

import pytest

from application.dtos.admissions import AdmissionResult
from application.dtos.reception import IngestLeadCommand
from application.ports.output.admissions import AdmissionUnavailable
from application.use_cases.records.ingest_lead import IngestLeadUseCase
from application.use_cases.reception.payloads import command_from_record
from domain.exceptions import DomainException
from domain.records.intake_record import IntakeRecord
from domain.value_objects.lead_id import LeadId
from domain.value_objects.enums import IntakeRecordStatus
from tests.unit.application.doubles.admissions import FakeLeadAdmission, admitted, rejected, unavailable
from tests.unit.application.doubles.uow import InMemoryUnitOfWork

_PAYLOAD = {"first_name": "Maria", "last_name": "Gomez", "company": "TechCorp", "budget": 5000,
            "industry": "Tech", "email": "mgomez@techcorp.com"}


def _record(uow: InMemoryUnitOfWork, payload: dict | None = None, **fields) -> IntakeRecord:
    return uow.intake_records.save(IntakeRecord.create(
        tenant_id=uuid4(), source_id=uuid4(), payload=_PAYLOAD if payload is None else payload, **fields,
    ))


def _ingest(uow, admission, record):
    return IngestLeadUseCase(uow, admission).execute(command_from_record(record), existing_record=record)


def _stored(uow, record) -> IntakeRecord:
    return uow.intake_records.get_by_id_and_tenant(record.id.value, record.tenant_id.value)


def test_an_admitted_record_is_promoted_to_the_lead_lead_core_created():
    uow, lead_id = InMemoryUnitOfWork(), str(uuid4())
    admission = FakeLeadAdmission(uow, lambda _: admitted(lead_id, score=70, assigned_agent_id="a-1",
                                                          applied_rules_count=2))
    record = _record(uow)

    result = _ingest(uow, admission, record)

    assert (result.lead_id, result.status, result.score) == (lead_id, "QUALIFIED", 70)
    assert (result.assigned_agent_id, result.applied_rules_count, result.error) == ("a-1", 2, None)
    assert result.intake_record_id == str(record.id)
    stored = _stored(uow, record)
    assert stored.status == IntakeRecordStatus.PROMOTED and str(stored.lead_id) == lead_id
    assert uow.events() == []


def test_a_rejection_closes_the_record_with_the_errors_and_records_intake_rejected():
    uow = InMemoryUnitOfWork()
    record = _record(uow)

    result = _ingest(uow, FakeLeadAdmission(uow, lambda _: rejected("email", "Invalid email", "INVALID_EMAIL")), record)

    assert (result.lead_id, result.status, result.error, result.error_code) == (
        "", "REJECTED", "Invalid email", "INVALID_EMAIL")
    stored = _stored(uow, record)
    assert stored.status == IntakeRecordStatus.REJECTED and stored.lead_id is None
    assert [(e.field, e.message, e.error_code) for e in stored.errors] == [("email", "Invalid email", "INVALID_EMAIL")]
    [event] = uow.events("IntakeRejected")
    assert event.channel == "internal" and event.partition_key == str(record.id)
    assert event.payload == {"tenant_id": str(record.tenant_id.value), "intake_record_id": str(record.id),
                             "reason": "Invalid email"}


def test_lead_core_is_called_with_no_transaction_open():
    uow = InMemoryUnitOfWork()
    admission = FakeLeadAdmission(uow)

    _ingest(uow, admission, _record(uow))

    assert admission.open_transactions_at_call == [0]
    assert uow.open_transactions == 0


def test_the_request_takes_organization_and_source_from_the_record_not_the_payload():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    record = _record(uow, dict(_PAYLOAD, tenant_id=str(uuid4()), source_id=str(uuid4())))

    _ingest(uow, admission, record)

    [request] = admission.requests
    assert request.tenant_id == record.tenant_id.value
    assert request.source_id == record.source_id.value
    assert request.intake_record_id == record.id.value


def test_scalars_travel_as_text_and_a_float_budget_keeps_its_decimal_form():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    record = _record(uow, dict(_PAYLOAD, budget=1234.5, phone=600123456))

    _ingest(uow, admission, record)

    candidate = admission.requests[0].candidate
    assert (candidate.budget, candidate.phone, candidate.first_name) == ("1234.5", "600123456", "Maria")


def test_an_already_promoted_record_answers_with_its_lead_without_calling():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    lead_id = uuid4()
    record = _record(uow, status=IntakeRecordStatus.PROMOTED, lead_id=lead_id)

    result = _ingest(uow, admission, record)

    assert (result.lead_id, result.status) == (str(lead_id), "PROMOTED")
    assert admission.requests == []


def test_losing_the_claim_answers_with_the_winners_lead_and_writes_nothing():
    uow, lead_id = InMemoryUnitOfWork(), uuid4()
    record = _record(uow)

    def other_run_wins(_):
        # Between the call and the claim, another run closes the same record.
        stored = _stored(uow, record)
        stored.promote(lead_id)
        uow.intake_records.save(stored)
        return admitted(str(lead_id))

    result = _ingest(uow, FakeLeadAdmission(uow, other_run_wins), record)

    assert (result.lead_id, result.status) == (str(lead_id), "PROMOTED")
    assert uow.events() == []


def test_an_unavailable_lead_core_propagates_and_leaves_the_record_pending():
    uow = InMemoryUnitOfWork()
    record = _record(uow)

    with pytest.raises(AdmissionUnavailable):
        _ingest(uow, FakeLeadAdmission(uow, unavailable), record)

    assert _stored(uow, record).status == IntakeRecordStatus.PENDING
    assert uow.events() == []


@pytest.mark.parametrize("answer", [
    AdmissionResult(outcome="ADMITTED"), AdmissionResult(outcome="REJECTED"), AdmissionResult(outcome="MAYBE"),
])
def test_an_answer_that_is_not_a_decision_counts_as_unavailable(answer):
    uow = InMemoryUnitOfWork()
    record = _record(uow)

    with pytest.raises(AdmissionUnavailable):
        _ingest(uow, FakeLeadAdmission(uow, lambda _: answer), record)

    assert _stored(uow, record).status == IntakeRecordStatus.PENDING


def test_a_discarded_record_is_refused_before_asking_lead_core():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    record = _record(uow, status=IntakeRecordStatus.DISCARDED)

    with pytest.raises(DomainException) as caught:
        _ingest(uow, admission, record)

    assert caught.value.error_code == "INVALID_INTAKE_TRANSITION"
    assert admission.requests == []


def test_a_rejected_record_can_be_admitted_after_a_correction():
    uow = InMemoryUnitOfWork()
    record = _record(uow)
    _ingest(uow, FakeLeadAdmission(uow, lambda _: rejected()), record)

    result = _ingest(uow, FakeLeadAdmission(uow), record)

    assert result.status == "QUALIFIED"
    assert _stored(uow, record).status == IntakeRecordStatus.PROMOTED


def test_a_failed_commit_takes_the_recorded_rejection_with_it():
    class _CommitFails(InMemoryUnitOfWork):
        def commit(self) -> None:
            self.rollback()
            raise RuntimeError("commit refused")

    uow = _CommitFails()
    record = _record(uow)

    with pytest.raises(RuntimeError):
        _ingest(uow, FakeLeadAdmission(uow, lambda _: rejected()), record)

    assert uow.events() == []


def test_a_command_with_missing_fields_still_builds_a_request():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    record = _record(uow, {})

    IngestLeadUseCase(uow, admission).execute(
        IngestLeadCommand(tenant_id=uuid4(), source_id=uuid4()), existing_record=record,
    )

    assert admission.requests[0].candidate.email is None
    assert isinstance(admission.requests[0].intake_record_id, UUID)


def test_a_stale_record_in_hand_is_judged_by_what_the_store_says_before_asking():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    lead_id = uuid4()
    stale = _record(uow)
    stored = _stored(uow, stale)
    stored.status, stored.lead_id = IntakeRecordStatus.PROMOTED, LeadId(lead_id)
    uow.intake_records.save(stored)

    result = _ingest(uow, admission, stale)

    assert (result.lead_id, result.status) == (str(lead_id), "PROMOTED")
    assert admission.requests == []


def test_a_record_discarded_since_it_was_read_is_refused_before_asking():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    stale = _record(uow)
    stored = _stored(uow, stale)
    stored.discard()
    uow.intake_records.save(stored)

    with pytest.raises(DomainException) as caught:
        _ingest(uow, admission, stale)

    assert caught.value.error_code == "INVALID_INTAKE_TRANSITION"
    assert admission.requests == []


def test_a_record_that_no_longer_exists_is_not_found_before_asking():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    ghost = IntakeRecord.create(tenant_id=uuid4(), source_id=uuid4(), payload=_PAYLOAD)

    with pytest.raises(DomainException) as caught:
        _ingest(uow, admission, ghost)

    assert caught.value.error_code == "INTAKE_RECORD_NOT_FOUND"
    assert admission.requests == []


def test_a_discard_that_lands_before_the_claim_is_refused_and_writes_nothing():
    uow = InMemoryUnitOfWork()
    record = _record(uow)

    def discarded_meanwhile(_):
        stored = _stored(uow, record)
        stored.discard()
        uow.intake_records.save(stored)
        return rejected()

    with pytest.raises(DomainException) as caught:
        _ingest(uow, FakeLeadAdmission(uow, discarded_meanwhile), record)

    assert caught.value.error_code == "INVALID_INTAKE_TRANSITION"
    assert _stored(uow, record).status == IntakeRecordStatus.DISCARDED
    assert uow.events() == []
