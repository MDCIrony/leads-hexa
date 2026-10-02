from uuid import uuid4

import pytest

from application.dtos.records import GetIntakeRecordsQuery, PromoteIntakeRecordCommand
from application.use_cases.records.ingest_lead import IngestLeadUseCase
from application.use_cases.records.manage_records import (
    DiscardIntakeRecordUseCase,
    GetIntakeRecordsUseCase,
    PromoteIntakeRecordUseCase,
)
from domain.exceptions import DomainException
from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from tests.unit.application.doubles.admissions import FakeLeadAdmission, admitted, rejected, unavailable
from tests.unit.application.doubles.uow import InMemoryUnitOfWork

_CORRECTED = {"first_name": "Maria", "last_name": "Gomez", "company": "TechCorp", "budget": "5000",
              "industry": "Tech", "email": "maria@techcorp.com"}


def _record(uow: InMemoryUnitOfWork, tenant_id=None, **fields) -> IntakeRecord:
    return uow.intake_records.save(IntakeRecord.create(
        tenant_id=tenant_id or uuid4(), source_id=uuid4(), payload={"email": "typo"}, **fields,
    ))


def _promote(uow, admission, record, payload=None, tenant_id=None):
    return PromoteIntakeRecordUseCase(uow, IngestLeadUseCase(uow, admission)).execute(PromoteIntakeRecordCommand(
        tenant_id=tenant_id or record.tenant_id.value, record_id=record.id.value, payload=payload or _CORRECTED,
    ))


def test_promoting_asks_lead_core_with_the_corrected_payload_over_the_records_source():
    uow = InMemoryUnitOfWork()
    admission = FakeLeadAdmission(uow)
    record = _record(uow, status=IntakeRecordStatus.REJECTED)

    result = _promote(uow, admission, record)

    [request] = admission.requests
    assert request.candidate.email == "maria@techcorp.com"
    assert request.source_id == record.source_id.value
    assert result.status == "QUALIFIED"
    assert record.status == IntakeRecordStatus.PROMOTED


def test_a_promotion_lead_core_rejects_comes_back_as_a_rejected_result_not_an_error():
    uow = InMemoryUnitOfWork()
    record = _record(uow)

    result = _promote(uow, FakeLeadAdmission(uow, lambda _: rejected()), record)

    assert (result.status, result.error_code) == ("REJECTED", "INVALID_EMAIL")


def test_promoting_with_lead_core_down_surfaces_lead_core_unavailable():
    uow = InMemoryUnitOfWork()
    record = _record(uow)

    with pytest.raises(DomainException) as caught:
        _promote(uow, FakeLeadAdmission(uow, unavailable), record)

    assert caught.value.error_code == "LEAD_CORE_UNAVAILABLE"
    assert record.status == IntakeRecordStatus.PENDING


def test_promoting_a_promoted_record_is_refused_without_calling_lead_core():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    record = _record(uow, status=IntakeRecordStatus.PROMOTED, lead_id=uuid4())

    with pytest.raises(DomainException) as caught:
        _promote(uow, admission, record)

    assert caught.value.error_code == "INVALID_INTAKE_TRANSITION"
    assert admission.requests == []


def test_a_record_of_another_organization_is_not_found():
    uow, admission = InMemoryUnitOfWork(), FakeLeadAdmission()
    record = _record(uow)

    for action in (
        lambda: _promote(uow, admission, record, tenant_id=uuid4()),
        lambda: DiscardIntakeRecordUseCase(uow).execute(uuid4(), record.id.value),
    ):
        with pytest.raises(DomainException) as caught:
            action()
        assert caught.value.error_code == "INTAKE_RECORD_NOT_FOUND"
    assert admission.requests == []


def test_discarding_closes_a_record_and_a_closed_one_cannot_be_discarded_again():
    uow = InMemoryUnitOfWork()
    record = _record(uow)

    DiscardIntakeRecordUseCase(uow).execute(record.tenant_id.value, record.id.value)

    assert record.status == IntakeRecordStatus.DISCARDED
    with pytest.raises(DomainException) as caught:
        DiscardIntakeRecordUseCase(uow).execute(record.tenant_id.value, record.id.value)
    assert caught.value.error_code == "INVALID_INTAKE_TRANSITION"


def test_listing_filters_by_status_and_job_and_counts_the_whole_match():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    job_id = uuid4()
    _record(uow, tenant_id, job_id=job_id)
    _record(uow, tenant_id, job_id=job_id, status=IntakeRecordStatus.REJECTED)
    _record(uow, tenant_id)
    _record(uow)

    page = GetIntakeRecordsUseCase(uow).execute(
        GetIntakeRecordsQuery(tenant_id=tenant_id, status="PENDING", limit=1))
    by_job = GetIntakeRecordsUseCase(uow).execute(GetIntakeRecordsQuery(tenant_id=tenant_id, job_id=job_id))

    assert (len(page.items), page.total, by_job.total) == (1, 2, 2)


def test_listing_by_an_unknown_status_is_a_domain_error():
    with pytest.raises(DomainException) as caught:
        GetIntakeRecordsUseCase(InMemoryUnitOfWork()).execute(GetIntakeRecordsQuery(uuid4(), status="NOPE"))
    assert caught.value.error_code == "INVALID_INTAKE_STATUS"
