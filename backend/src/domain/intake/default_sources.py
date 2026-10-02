from typing import List

from domain.entities.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind
from domain.value_objects.tenant_id import TenantId

DEFAULT_SOURCES = (
    ("Formulario manual", LeadSourceKind.MANUAL_FORM),
    ("Carga de fichero", LeadSourceKind.FILE_UPLOAD),
)


def default_sources(tenant_id: TenantId) -> List[LeadSource]:
    """The sources every organization starts with, so it can receive leads from day one."""
    return [LeadSource.create(tenant_id=tenant_id, name=name, kind=kind) for name, kind in DEFAULT_SOURCES]
