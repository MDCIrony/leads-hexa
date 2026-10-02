from uuid import uuid4

import pytest

from application.dtos.sources import CreateLeadSourceCommand, GetLeadSourcesQuery, UpdateLeadSourceCommand
from application.use_cases.sources.lead_sources import (
    CreateLeadSourceUseCase,
    DeleteLeadSourceUseCase,
    GetLeadSourcesUseCase,
    UpdateLeadSourceUseCase,
)
from domain.exceptions import DomainException
from domain.records.intake_record import IntakeRecord
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _create(uow, tenant_id, name="Landing"):
    return CreateLeadSourceUseCase(uow).execute(
        CreateLeadSourceCommand(tenant_id=tenant_id, name=name, kind="WEBHOOK"))


def _code(action) -> str:
    with pytest.raises(DomainException) as caught:
        action()
    return caught.value.error_code


def test_a_created_source_is_active_and_listed_for_its_organization_only():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    source = _create(uow, tenant_id)
    _create(uow, uuid4())

    page = GetLeadSourcesUseCase(uow).execute(GetLeadSourcesQuery(tenant_id=tenant_id))

    assert source.is_active and [s.id for s in page.items] == [source.id] and page.total == 1


def test_a_name_is_unique_within_an_organization_but_not_across_them():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    _create(uow, tenant_id)
    _create(uow, uuid4())

    assert _code(lambda: _create(uow, tenant_id, name="  Landing ")) == "SOURCE_ALREADY_EXISTS"


def test_a_page_reports_the_total_beyond_the_limit():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    for name in ("A", "B", "C"):
        _create(uow, tenant_id, name)

    page = GetLeadSourcesUseCase(uow).execute(GetLeadSourcesQuery(tenant_id=tenant_id, limit=2))

    assert (len(page.items), page.total) == (2, 3)


def test_an_update_changes_only_what_it_sends():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    source = _create(uow, tenant_id)

    updated = UpdateLeadSourceUseCase(uow).execute(
        UpdateLeadSourceCommand(tenant_id=tenant_id, source_id=source.id.value, is_active=False))

    assert (updated.name, updated.is_active) == ("Landing", False)


def test_a_source_of_another_organization_is_not_found():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    source = _create(uow, tenant_id)

    assert _code(lambda: UpdateLeadSourceUseCase(uow).execute(
        UpdateLeadSourceCommand(tenant_id=uuid4(), source_id=source.id.value, name="X"))) == "SOURCE_NOT_FOUND"
    assert _code(lambda: DeleteLeadSourceUseCase(uow).execute(uuid4(), source.id.value)) == "SOURCE_NOT_FOUND"


def test_a_source_with_intake_records_cannot_be_deleted():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    source = _create(uow, tenant_id)
    uow.intake_records.save(IntakeRecord.create(tenant_id=tenant_id, source_id=source.id.value, payload={}))

    assert _code(lambda: DeleteLeadSourceUseCase(uow).execute(tenant_id, source.id.value)) == "SOURCE_IN_USE"
    assert uow.sources.get_by_id_and_tenant(source.id.value, tenant_id) is not None


def test_a_source_without_records_is_deleted():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    source = _create(uow, tenant_id)

    DeleteLeadSourceUseCase(uow).execute(tenant_id, source.id.value)

    assert uow.sources.get_by_id_and_tenant(source.id.value, tenant_id) is None
