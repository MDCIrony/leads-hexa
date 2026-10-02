from abc import ABC
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict
from uuid import UUID, uuid4


def _jsonable(value: Any) -> Any:
    """One value, turned into whatever JSON (and JSONB) can hold.

    Decimal included even though no event field is one today: the moment a
    money field becomes an event field, a float here would throw away the
    exactness the column type exists to protect."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


@dataclass(kw_only=True)
class DomainEvent(ABC):
    """Base class for all domain events."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_on: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    def as_payload(self) -> Dict[str, Any]:
        """The event as JSON-ready data, whatever transport ends up carrying it."""
        return {key: _jsonable(value) for key, value in asdict(self).items()}
