import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.criterion import Criterion, all_match

if TYPE_CHECKING:
    from domain.entities.lead import Lead


@dataclass
class DisqualificationRule:
    """Says a lead cannot be worked at all, and why.

    Viability is a binary question, so it gets a binary tool instead of a
    number: expressing "no way of contacting them" as a -9999 penalty let any
    other rule rescue the lead by accident."""

    id: UUID
    tenant_id: UUID
    name: str
    conditions: List[Criterion]
    priority: int = 0
    is_active: bool = True

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        conditions: List[Union[Criterion, Dict[str, Any]]],
        priority: int = 0,
        is_active: bool = True,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "DisqualificationRule":
        clean_name = (name or "").strip()
        if not clean_name:
            raise DomainException(
                "La regla necesita un nombre: es el motivo que verá el gestor",
                error_code="INVALID_RULE_NAME",
            )
        parsed = [c if isinstance(c, Criterion) else Criterion.from_dict(c) for c in conditions]
        if not parsed:
            # A rule with no conditions holds for every lead, so it would
            # disqualify the entire organization on the next ingestion.
            raise DomainException(
                "Una regla de descalificación necesita al menos una condición",
                error_code="INVALID_RULE_CONDITIONS",
            )
        return cls(
            id=UUID(str(rule_id)) if rule_id else uuid.uuid4(),
            tenant_id=UUID(str(tenant_id)),
            name=clean_name,
            conditions=parsed,
            priority=priority,
            is_active=is_active,
        )

    def matches(self, lead: "Lead") -> bool:
        return all_match(self.conditions, lead)
