from dataclasses import dataclass
from uuid import UUID

from domain.notifications.notification import Notification


@dataclass(frozen=True)
class GetNotificationsQuery:
    recipient_id: UUID
    unread_only: bool = False
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class MarkNotificationReadCommand:
    recipient_id: UUID
    notification_id: UUID


@dataclass(frozen=True)
class NotificationsPageResult:
    items: list[Notification]
    total: int
    unread_count: int
