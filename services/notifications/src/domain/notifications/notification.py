from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.exceptions import DomainException
from domain.notifications.kind import NotificationKind


def _as_uuid(value: str | UUID) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except ValueError:
        raise DomainException(f"Invalid identifier: {value!r}", error_code="INVALID_IDENTIFIER") from None


def _validate_message(message: str) -> str:
    clean = (message or "").strip()
    if not clean:
        raise DomainException("A notification requires a message", error_code="INVALID_NOTIFICATION_MESSAGE")
    return clean


@dataclass
class Notification:
    id: UUID
    tenant_id: UUID
    recipient_id: UUID
    kind: NotificationKind
    message: str
    lead_id: UUID | None = None
    intake_record_id: UUID | None = None
    is_read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: str | UUID,
        recipient_id: str | UUID,
        kind: str | NotificationKind,
        message: str,
        lead_id: str | UUID | None = None,
        intake_record_id: str | UUID | None = None,
        notification_id: str | UUID | None = None,
        is_read: bool = False,
        created_at: datetime | None = None,
    ) -> "Notification":
        """Builds a notice from raw identifiers and enforces its invariants."""
        return cls(
            id=_as_uuid(notification_id) if notification_id is not None else uuid4(),
            tenant_id=_as_uuid(tenant_id),
            recipient_id=_as_uuid(recipient_id),
            kind=NotificationKind(kind),
            message=_validate_message(message),
            lead_id=_as_uuid(lead_id) if lead_id is not None else None,
            intake_record_id=_as_uuid(intake_record_id) if intake_record_id is not None else None,
            is_read=is_read,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def mark_as_read(self) -> None:
        # Idempotent on purpose: "mark all as read" walks every notice and
        # re-marking one already read is the normal case, not an error.
        self.is_read = True
