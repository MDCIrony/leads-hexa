from uuid import UUID, uuid4

import pytest

from application.dtos.reception import ReceiveIntakeCommand
from application.dtos.records import LeadProcessedResult
from application.ports.input.reception import IngestLeadInputPort
from application.use_cases.jobs.process_intake_job import ProcessIntakeJobUseCase
from application.use_cases.reception.receive_intake import ReceiveIntakeUseCase
from application.use_cases.records.ingest_lead import IngestLeadUseCase
from domain.exceptions import DomainException
from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus, IntakeRecordStatus, LeadSourceKind
from tests.unit.application.doubles.admissions import FakeLeadAdmission, rejected, unavailable
from tests.unit.application.doubles.uow import InMemoryUnitOfWork

_VALID = {"first_name": "Maria", "last_name": "Gomez", "company": "TechCorp", "budget": 5000,
          "industry": "Tech", "email": "mgomez@techcorp.com"}
_INVALID = dict(_VALID, email="not-an-email")


def _received(payloads, kind=IntakeJobKind.BATCH):
    tenant_id = uuid4()
    uow = InMemoryUnitOfWork()
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Upload", kind=LeadSourceKind.FILE_UPLOAD))
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Form", kind=LeadSourceKind.MANUAL_FORM))
    result = ReceiveIntakeUseCase(uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=kind.value, payloads=payloads))
    return uow, tenant_id, UUID(result.job_id), [UUID(r) for r in result.record_ids]


def _process(uow, admission, tenant_id, job_id) -> bool:
    return ProcessIntakeJobUseCase(uow, IngestLeadUseCase(uow, admission)).execute(tenant_id, job_id)


def _status(uow, tenant_id, record_id):
    return uow.intake_records.get_by_id_and_tenant(record_id, tenant_id).status


def test_a_job_counts_what_lead_core_admitted_and_what_it_rejected():
    uow, tenant_id, job_id, records = _received([_VALID, _INVALID])
    admission = FakeLeadAdmission(
        uow, lambda r: rejected() if r.candidate.email == "not-an-email" else FakeLeadAdmission().admit(r))

    interrupted = _process(uow, admission, tenant_id, job_id)

    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (interrupted, job.status, job.succeeded, job.failed) == (False, IntakeJobStatus.COMPLETED, 1, 1)
    assert {_status(uow, tenant_id, r) for r in records} == {IntakeRecordStatus.PROMOTED, IntakeRecordStatus.REJECTED}
    assert admission.open_transactions_at_call == [0, 0]


def test_a_job_of_another_organization_is_not_found():
    uow, _, job_id, _ = _received([_VALID])

    with pytest.raises(DomainException) as caught:
        _process(uow, FakeLeadAdmission(uow), uuid4(), job_id)

    assert caught.value.error_code == "INTAKE_JOB_NOT_FOUND"


def test_lead_core_down_leaves_every_record_pending_and_the_job_interrupted():
    uow, tenant_id, job_id, records = _received([_VALID, dict(_VALID, email="b@techcorp.com")])

    interrupted = _process(uow, FakeLeadAdmission(uow, unavailable), tenant_id, job_id)

    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    # PROCESSING, not COMPLETED: a completed job would refuse the reprocess that picks these up.
    assert (interrupted, job.status, job.succeeded, job.failed) == (True, IntakeJobStatus.PROCESSING, 0, 0)
    assert [_status(uow, tenant_id, r) for r in records] == [IntakeRecordStatus.PENDING] * 2
    assert uow.events("IntakeRejected") == []


def test_the_first_outage_stops_the_run_without_asking_about_the_rest():
    uow, tenant_id, job_id, records = _received([dict(_VALID, email=f"{n}@techcorp.com") for n in range(3)])
    admission = FakeLeadAdmission(uow, unavailable)

    interrupted = _process(uow, admission, tenant_id, job_id)

    assert interrupted is True
    assert len(admission.requests) == 1
    assert [_status(uow, tenant_id, r) for r in records] == [IntakeRecordStatus.PENDING] * 3
    assert uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id).status == IntakeJobStatus.PROCESSING


def test_an_unforeseen_failure_on_one_record_does_not_stop_the_rest():
    uow, tenant_id, job_id, records = _received([dict(_VALID, email="boom@x.co"), _VALID])
    real = IngestLeadUseCase(uow, FakeLeadAdmission(uow))

    class _Exploding(IngestLeadInputPort):
        def execute(self, command, existing_record) -> LeadProcessedResult:
            if command.email == "boom@x.co":
                raise RuntimeError("boom")
            return real.execute(command, existing_record)

    interrupted = ProcessIntakeJobUseCase(uow, _Exploding()).execute(tenant_id, job_id)

    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (interrupted, job.succeeded, job.failed) == (True, 1, 0)
    assert [_status(uow, tenant_id, r) for r in records] == [IntakeRecordStatus.PENDING, IntakeRecordStatus.PROMOTED]


def test_running_again_after_an_interruption_finishes_the_job():
    uow, tenant_id, job_id, records = _received([_VALID])
    _process(uow, FakeLeadAdmission(uow, unavailable), tenant_id, job_id)

    interrupted = _process(uow, FakeLeadAdmission(uow), tenant_id, job_id)

    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (interrupted, job.status, job.succeeded) == (False, IntakeJobStatus.COMPLETED, 1)


def test_a_redelivered_job_does_not_ask_lead_core_about_records_already_promoted():
    uow, tenant_id, job_id, _ = _received([_VALID])
    admission = FakeLeadAdmission(uow)
    _process(uow, admission, tenant_id, job_id)
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    job.status = IntakeJobStatus.PROCESSING  # what a worker that died after the last record leaves
    uow.intake_jobs.save(job)

    _process(uow, admission, tenant_id, job_id)

    assert len(admission.requests) == 1


def test_counters_are_recovered_from_the_records_after_a_run_that_died_before_saving_them():
    uow, tenant_id, job_id, _ = _received([_VALID, dict(_VALID, email="second@techcorp.com")])
    admission = FakeLeadAdmission(uow)
    _process(uow, admission, tenant_id, job_id)
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    job.status, job.succeeded, job.failed, job.completed_at = IntakeJobStatus.PROCESSING, 0, 0, None
    uow.intake_jobs.save(job)

    _process(uow, admission, tenant_id, job_id)

    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (job.succeeded, job.failed) == (2, 0)


def test_a_record_discarded_mid_batch_is_skipped_and_does_not_interrupt_the_job():
    uow, tenant_id, job_id, records = _received([_VALID, dict(_VALID, email="second@techcorp.com")])
    real = IngestLeadUseCase(uow, FakeLeadAdmission(uow))

    class _DiscardedMeanwhile(IngestLeadInputPort):
        def execute(self, command, existing_record) -> LeadProcessedResult:
            if command.email == _VALID["email"]:
                discarded = uow.intake_records.get_by_id_and_tenant(existing_record.id.value, tenant_id)
                discarded.discard()
                uow.intake_records.save(discarded)
            return real.execute(command, existing_record)

    interrupted = ProcessIntakeJobUseCase(uow, _DiscardedMeanwhile()).execute(tenant_id, job_id)

    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (interrupted, job.status, job.succeeded, job.failed) == (False, IntakeJobStatus.COMPLETED, 1, 0)
    assert {_status(uow, tenant_id, r) for r in records} == {IntakeRecordStatus.DISCARDED, IntakeRecordStatus.PROMOTED}
