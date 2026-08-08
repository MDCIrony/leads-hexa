import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.tenant_id import TenantId

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Turn a display name into a stable, URL-safe identifier.

    Accents are folded rather than dropped so that "Solución" and "Solucion"
    collapse to the same slug instead of producing two organizations that read
    identically to a human."""
    folded = unicodedata.normalize("NFKD", value)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALPHANUMERIC.sub("-", ascii_only).strip("-")
    if not slug:
        raise DomainException(
            "El nombre no contiene caracteres utilizables para un identificador",
            error_code="INVALID_TENANT_NAME",
        )
    return slug


@dataclass
class Tenant:
    id: TenantId
    name: str
    slug: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        name: str,
        tenant_id: Optional[Union[str, UUID, TenantId]] = None,
        slug: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
    ) -> "Tenant":
        clean_name = _require_name(name)
        identifier = tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id)
        return cls(
            id=identifier,
            name=clean_name,
            slug=slug or slugify(clean_name),
            is_active=is_active,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def rename(self, name: str) -> None:
        # The slug deliberately stays put: it is what other records reference.
        self.name = _require_name(name)


def _require_name(name: str) -> str:
    clean = (name or "").strip()
    if not clean:
        raise DomainException(
            "El nombre de la organización no puede estar vacío",
            error_code="INVALID_TENANT_NAME",
        )
    return clean
