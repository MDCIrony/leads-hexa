import uuid

from domain.sources.default_sources import default_sources
from domain.value_objects.enums import LeadSourceKind
from domain.value_objects.tenant_id import TenantId


def test_an_organization_starts_with_a_manual_form_and_a_file_upload():
    tenant_id = TenantId(str(uuid.uuid4()))

    sources = default_sources(tenant_id)

    assert sorted((s.name, s.kind) for s in sources) == [
        ("Carga de fichero", LeadSourceKind.FILE_UPLOAD),
        ("Formulario manual", LeadSourceKind.MANUAL_FORM),
    ]
    assert all(s.tenant_id == tenant_id and s.is_active for s in sources)


def test_each_call_builds_new_sources():
    tenant_id = TenantId()

    assert {s.id for s in default_sources(tenant_id)}.isdisjoint({s.id for s in default_sources(tenant_id)})
