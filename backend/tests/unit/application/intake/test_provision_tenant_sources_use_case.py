import uuid

import pytest

from application.use_cases.intake.provision_tenant_sources import ProvisionTenantSourcesUseCase
from domain.entities.lead_source import LeadSource
from domain.exceptions import InvalidUUIDException
from domain.value_objects.enums import LeadSourceKind
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _payload(tenant_id: uuid.UUID, is_active: bool = True) -> dict:
    return {"tenant_id": str(tenant_id), "name": "Acme", "slug": "acme", "is_active": is_active, "version": 1}


def _sources(uow: InMemoryUnitOfWork, tenant_id: uuid.UUID) -> list:
    return sorted((source.name, source.kind) for source in uow.sources.list_by_tenant(tenant_id))


def test_a_new_tenant_gets_the_two_default_sources_and_is_marked():
    uow, tenant_id = InMemoryUnitOfWork(), uuid.uuid4()

    assert ProvisionTenantSourcesUseCase().apply(_payload(tenant_id), uow) is True

    assert _sources(uow, tenant_id) == [
        ("Carga de fichero", LeadSourceKind.FILE_UPLOAD), ("Formulario manual", LeadSourceKind.MANUAL_FORM)]
    assert tenant_id in uow.provisioned_tenants.tenant_ids


def test_a_second_state_of_the_same_tenant_creates_nothing():
    uow, tenant_id = InMemoryUnitOfWork(), uuid.uuid4()
    ProvisionTenantSourcesUseCase().apply(_payload(tenant_id), uow)

    assert ProvisionTenantSourcesUseCase().apply(_payload(tenant_id), uow) is False

    assert len(_sources(uow, tenant_id)) == 2


def test_a_provisioned_tenant_does_not_get_a_deleted_source_back():
    uow, tenant_id = InMemoryUnitOfWork(), uuid.uuid4()
    ProvisionTenantSourcesUseCase().apply(_payload(tenant_id), uow)
    for source in uow.sources.list_by_tenant(tenant_id):
        uow.sources.delete(source.id.value, tenant_id)

    assert ProvisionTenantSourcesUseCase().apply(_payload(tenant_id), uow) is False

    assert _sources(uow, tenant_id) == []


def test_an_inactive_tenant_is_marked_without_sources():
    uow, tenant_id = InMemoryUnitOfWork(), uuid.uuid4()

    assert ProvisionTenantSourcesUseCase().apply(_payload(tenant_id, is_active=False), uow) is False

    assert _sources(uow, tenant_id) == []
    assert ProvisionTenantSourcesUseCase().apply(_payload(tenant_id), uow) is False
    assert _sources(uow, tenant_id) == []


def test_a_tenant_the_monolith_already_provisioned_is_only_marked():
    uow, tenant_id = InMemoryUnitOfWork(), uuid.uuid4()
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Formulario manual", kind=LeadSourceKind.MANUAL_FORM))

    assert ProvisionTenantSourcesUseCase().apply(_payload(tenant_id), uow) is False

    assert _sources(uow, tenant_id) == [("Formulario manual", LeadSourceKind.MANUAL_FORM)]
    assert tenant_id in uow.provisioned_tenants.tenant_ids


@pytest.mark.parametrize("changes", [
    {"tenant_id": None}, {"tenant_id": 42}, {"is_active": None}, {"is_active": "true"},
])
def test_a_malformed_state_is_rejected_before_any_write(changes):
    uow, payload = InMemoryUnitOfWork(), {**_payload(uuid.uuid4()), **changes}

    with pytest.raises(ValueError):
        ProvisionTenantSourcesUseCase().apply(payload, uow)

    assert uow.provisioned_tenants.tenant_ids == set()


def test_a_state_without_tenant_id_is_rejected():
    uow, payload = InMemoryUnitOfWork(), _payload(uuid.uuid4())
    del payload["tenant_id"]

    with pytest.raises(ValueError):
        ProvisionTenantSourcesUseCase().apply(payload, uow)


def test_a_tenant_id_that_is_not_a_uuid_is_rejected():
    with pytest.raises(InvalidUUIDException):
        ProvisionTenantSourcesUseCase().apply({**_payload(uuid.uuid4()), "tenant_id": "acme"}, InMemoryUnitOfWork())
