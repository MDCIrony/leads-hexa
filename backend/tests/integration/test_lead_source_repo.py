from types import SimpleNamespace

import psycopg
import pytest

from domain.value_objects.tenant_id import TenantId
from domain.entities.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlLeadSourceRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> SimpleNamespace:
    # No row: since migration 017 nothing in leads_db references tenants.
    return SimpleNamespace(id=TenantId())


def test_saves_and_reads_back_every_field(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        saved = repo.save(
            LeadSource.create(
                tenant_id=tenant.id.value,
                name="Formulario web",
                kind=LeadSourceKind.MANUAL_FORM,
                field_mapping={"nombre": "first_name"},
            )
        )

        found = repo.get_by_id_and_tenant(saved.id.value, tenant.id.value)
        assert found is not None
        assert found.name == "Formulario web"
        assert found.kind == LeadSourceKind.MANUAL_FORM
        assert found.field_mapping == {"nombre": "first_name"}
        assert found.is_active is True
        assert found.tenant_id.value == tenant.id.value
    finally:
        ctx.__exit__(None, None, None)


def test_reading_a_source_of_another_organization_returns_nothing(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        other = _tenant(conn)
        source = repo.save(
            LeadSource.create(tenant_id=tenant.id.value, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
        )

        assert repo.get_by_id_and_tenant(source.id.value, tenant.id.value) is not None
        assert repo.get_by_id_and_tenant(source.id.value, other.id.value) is None
    finally:
        ctx.__exit__(None, None, None)


def test_get_by_kind_resolves_the_automatic_source(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        repo.save(
            LeadSource.create(tenant_id=tenant.id.value, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
        )
        repo.save(
            LeadSource.create(tenant_id=tenant.id.value, name="Carga", kind=LeadSourceKind.FILE_UPLOAD)
        )

        found = repo.get_by_kind(tenant.id.value, LeadSourceKind.MANUAL_FORM)

        assert found is not None
        assert found.name == "Formulario"
    finally:
        ctx.__exit__(None, None, None)


def test_get_by_kind_returns_none_when_the_tenant_has_no_such_source(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        assert repo.get_by_kind(tenant.id.value, LeadSourceKind.MANUAL_FORM) is None
    finally:
        ctx.__exit__(None, None, None)


def test_listing_does_not_leak_into_another_organization(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant_a = _tenant(conn)
        tenant_b = _tenant(conn)
        repo.save(LeadSource.create(tenant_id=tenant_a.id.value, name="Norte", kind=LeadSourceKind.MANUAL_FORM))
        repo.save(LeadSource.create(tenant_id=tenant_a.id.value, name="Sur", kind=LeadSourceKind.FILE_UPLOAD))
        repo.save(LeadSource.create(tenant_id=tenant_b.id.value, name="Norte", kind=LeadSourceKind.MANUAL_FORM))

        found = repo.list_by_tenant(tenant_a.id.value)

        assert {s.name for s in found} == {"Norte", "Sur"}
    finally:
        ctx.__exit__(None, None, None)


def test_duplicate_name_within_the_same_organization_is_rejected(test_db):
    """The unique index is the real guarantee; application checks race."""
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        repo.save(
            LeadSource.create(tenant_id=tenant.id.value, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            repo.save(
                LeadSource.create(tenant_id=tenant.id.value, name="Formulario", kind=LeadSourceKind.FILE_UPLOAD)
            )
    finally:
        ctx.__exit__(None, None, None)


def test_deleting_a_source_of_another_organization_does_nothing(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        other = _tenant(conn)
        source = repo.save(
            LeadSource.create(tenant_id=tenant.id.value, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
        )

        assert repo.delete(source.id.value, other.id.value) is False
        assert repo.get_by_id_and_tenant(source.id.value, tenant.id.value) is not None

        assert repo.delete(source.id.value, tenant.id.value) is True
        assert repo.get_by_id_and_tenant(source.id.value, tenant.id.value) is None
    finally:
        ctx.__exit__(None, None, None)
