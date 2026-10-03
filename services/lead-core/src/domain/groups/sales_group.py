from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.enums import AssignmentStrategy
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId


@dataclass
class SalesGroup:
    """A set of sales agents that share an assignment policy.

    It replaces the free-form `team` string. A string cannot be renamed
    without orphaning every rule that named it, cannot carry a capacity, and
    turns a typo into a rule that silently matches nobody."""

    id: GroupId
    tenant_id: TenantId
    name: str
    description: Optional[str] = None
    default_strategy: AssignmentStrategy = AssignmentStrategy.LOWEST_LOAD
    capacity_per_agent: Optional[int] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        name: str,
        description: Optional[str] = None,
        default_strategy: Union[str, AssignmentStrategy] = AssignmentStrategy.LOWEST_LOAD,
        capacity_per_agent: Optional[int] = None,
        is_active: bool = True,
        group_id: Optional[Union[str, UUID, GroupId]] = None,
        created_at: Optional[datetime] = None,
    ) -> "SalesGroup":
        strategy = (
            default_strategy
            if isinstance(default_strategy, AssignmentStrategy)
            else AssignmentStrategy(default_strategy)
        )
        return cls(
            id=group_id if isinstance(group_id, GroupId) else GroupId(group_id),
            tenant_id=tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id),
            name=_require_name(name),
            description=description,
            default_strategy=strategy,
            capacity_per_agent=_validate_capacity(capacity_per_agent),
            is_active=is_active,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def rename(self, name: str) -> None:
        self.name = _require_name(name)

    def has_capacity_for(self, active_leads: int) -> bool:
        """Whether an agent carrying this many leads can take one more."""
        if self.capacity_per_agent is None:
            return True
        return active_leads < self.capacity_per_agent


def _require_name(name: str) -> str:
    clean = (name or "").strip()
    if not clean:
        raise DomainException(
            "El nombre del grupo no puede estar vacío",
            error_code="INVALID_GROUP_NAME",
        )
    return clean


def _validate_capacity(capacity: Optional[int]) -> Optional[int]:
    if capacity is not None and capacity <= 0:
        raise DomainException(
            "La capacidad por asesor debe ser mayor que cero",
            error_code="INVALID_GROUP_CAPACITY",
        )
    return capacity
