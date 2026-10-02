from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.enums import LeadSourceKind
from domain.value_objects.lead_source_id import LeadSourceId
from domain.value_objects.tenant_id import TenantId


def _validate_name(name: str) -> str:
    clean = (name or "").strip()
    if not clean:
        raise DomainException("El origen exige un nombre", error_code="SOURCE_WITHOUT_NAME")
    return clean


def _validate_field_mapping(mapping: Dict[str, str]) -> None:
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
            raise DomainException(
                "El mapeo de columnas exige claves y valores no vacíos",
                error_code="INVALID_FIELD_MAPPING",
            )


@dataclass
class LeadSource:
    id: LeadSourceId
    tenant_id: TenantId
    name: str
    kind: LeadSourceKind
    field_mapping: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True
    # Not a bare default: a datetime evaluated at class-definition time would freeze on import.
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        name: str,
        kind: Union[str, LeadSourceKind],
        field_mapping: Optional[Dict[str, str]] = None,
        is_active: bool = True,
        source_id: Optional[Union[str, UUID, LeadSourceId]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> "LeadSource":
        """Factory method that encapsulates Value Object construction and the
        source's invariants."""
        tenant_id_vo = tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id)
        kind_vo = kind if isinstance(kind, LeadSourceKind) else LeadSourceKind(kind)
        source_id_vo = source_id if isinstance(source_id, LeadSourceId) else LeadSourceId(source_id)
        mapping = field_mapping or {}

        clean_name = _validate_name(name)
        _validate_field_mapping(mapping)

        return cls(
            id=source_id_vo,
            tenant_id=tenant_id_vo,
            name=clean_name,
            kind=kind_vo,
            field_mapping=mapping,
            is_active=is_active,
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=updated_at or datetime.now(timezone.utc),
        )

    def rename(self, name: str) -> None:
        self.name = _validate_name(name)
        self._touch()

    def update_mapping(self, field_mapping: Dict[str, str]) -> None:
        _validate_field_mapping(field_mapping)
        self.field_mapping = field_mapping
        self._touch()

    def activate(self) -> None:
        self.is_active = True
        self._touch()

    def deactivate(self) -> None:
        self.is_active = False
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
