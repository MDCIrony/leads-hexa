from uuid import uuid4

import psycopg
import pytest

from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.output.persistence.lead_source_repository import PostgresLeadSourceRepository


def _form(tenant_id, name="Form"):
    return LeadSource.create(tenant_id=tenant_id, name=name, kind=LeadSourceKind.MANUAL_FORM)


def test_saves_and_reads_back_every_field(conn):
    repo, tenant_id = PostgresLeadSourceRepository(conn), uuid4()
    saved = repo.save(LeadSource.create(
        tenant_id=tenant_id, name="Web form", kind=LeadSourceKind.MANUAL_FORM, field_mapping={"nombre": "first_name"}))

    found = repo.get_by_id_and_tenant(saved.id.value, tenant_id)

    assert (found.name, found.kind, found.field_mapping, found.is_active) == (
        "Web form", LeadSourceKind.MANUAL_FORM, {"nombre": "first_name"}, True)
    assert found.tenant_id.value == tenant_id


def test_saving_again_updates_instead_of_duplicating(conn):
    repo, tenant_id = PostgresLeadSourceRepository(conn), uuid4()
    source = repo.save(_form(tenant_id))
    source.rename("Renamed")
    source.deactivate()
    repo.save(source)

    [found] = repo.list_by_tenant(tenant_id)

    assert (found.name, found.is_active) == ("Renamed", False)


def test_a_source_of_another_organization_reads_back_as_missing(conn):
    repo, tenant_id = PostgresLeadSourceRepository(conn), uuid4()
    source = repo.save(_form(tenant_id))

    assert repo.get_by_id_and_tenant(source.id.value, tenant_id) is not None
    assert repo.get_by_id_and_tenant(source.id.value, uuid4()) is None


def test_get_by_kind_resolves_the_oldest_source_of_the_kind(conn):
    repo, tenant_id = PostgresLeadSourceRepository(conn), uuid4()
    repo.save(_form(tenant_id, "First"))
    repo.save(_form(tenant_id, "Second"))
    repo.save(LeadSource.create(tenant_id=tenant_id, name="Upload", kind=LeadSourceKind.FILE_UPLOAD))

    assert repo.get_by_kind(tenant_id, LeadSourceKind.MANUAL_FORM).name == "First"
    assert repo.get_by_kind(uuid4(), LeadSourceKind.MANUAL_FORM) is None


def test_listing_does_not_leak_into_another_organization(conn):
    repo, tenant_a, tenant_b = PostgresLeadSourceRepository(conn), uuid4(), uuid4()
    repo.save(_form(tenant_a, "North"))
    repo.save(_form(tenant_a, "South"))
    repo.save(_form(tenant_b, "North"))

    assert [s.name for s in repo.list_by_tenant(tenant_a)] == ["North", "South"]
    assert [s.name for s in repo.list_by_tenant(tenant_a, limit=1, offset=1)] == ["South"]


def test_a_duplicate_name_within_one_organization_violates_the_unique_constraint(conn):
    # The constraint is the real guarantee; the use case's check races.
    repo, tenant_id = PostgresLeadSourceRepository(conn), uuid4()
    repo.save(_form(tenant_id))

    with pytest.raises(psycopg.errors.UniqueViolation):
        repo.save(_form(tenant_id))


def test_deleting_a_source_of_another_organization_does_nothing(conn):
    repo, tenant_id = PostgresLeadSourceRepository(conn), uuid4()
    source = repo.save(_form(tenant_id))

    assert repo.delete(source.id.value, uuid4()) is False
    assert repo.get_by_id_and_tenant(source.id.value, tenant_id) is not None
    assert repo.delete(source.id.value, tenant_id) is True
    assert repo.get_by_id_and_tenant(source.id.value, tenant_id) is None
