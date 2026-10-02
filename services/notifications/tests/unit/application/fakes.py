"""In-memory unit of work for the application tests. No database, no I/O."""
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from application.ports.output.member_repository import MemberRepositoryPort
from application.ports.output.notification_repository import NotificationRepositoryPort
from application.ports.output.processed_event_repository import ProcessedEventRepositoryPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.members.member import Member
from domain.notifications.notification import Notification


class InMemoryNotificationRepository(NotificationRepositoryPort):
    def __init__(self) -> None:
        self._notifications: Dict[UUID, Notification] = {}

    def save(self, notification: Notification) -> Notification:
        self._notifications[notification.id] = notification
        return notification

    def get_by_id_and_recipient(self, notification_id: UUID, recipient_id: UUID) -> Optional[Notification]:
        notification = self._notifications.get(notification_id)
        return notification if notification and notification.recipient_id == recipient_id else None

    def list_by_recipient(
        self, recipient_id: UUID, unread_only: bool = False, limit: int = 100, offset: int = 0
    ) -> List[Notification]:
        items = [n for n in self._notifications.values()
                 if n.recipient_id == recipient_id and (not unread_only or not n.is_read)]
        items.sort(key=lambda n: n.created_at, reverse=True)
        return items[offset:offset + limit]

    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int:
        return sum(1 for n in self._notifications.values()
                   if n.recipient_id == recipient_id and (not unread_only or not n.is_read))

    def mark_all_read(self, recipient_id: UUID) -> int:
        unread = [n for n in self._notifications.values() if n.recipient_id == recipient_id and not n.is_read]
        for notification in unread:
            notification.mark_as_read()
        return len(unread)


class InMemoryMemberRepository(MemberRepositoryPort):
    def __init__(self) -> None:
        self._members: Dict[UUID, Member] = {}

    def get(self, agent_id: UUID) -> Optional[Member]:
        return self._members.get(agent_id)

    def save(self, member: Member) -> None:
        self._members[member.agent_id] = member

    def active_manager_ids(self, tenant_id: UUID) -> list[UUID]:
        return [m.agent_id for m in self._members.values()
                if m.tenant_id == tenant_id and m.receives_organization_notices]


class InMemoryProcessedEventRepository(ProcessedEventRepositoryPort):
    def __init__(self) -> None:
        self._seen: Set[Tuple[str, UUID]] = set()

    def mark(self, consumer: str, event_id: UUID) -> bool:
        if (consumer, event_id) in self._seen:
            return False
        self._seen.add((consumer, event_id))
        return True


class InMemoryUnitOfWork(UnitOfWorkPort):
    def __init__(self) -> None:
        self.notifications = InMemoryNotificationRepository()
        self.members = InMemoryMemberRepository()
        self.processed_events = InMemoryProcessedEventRepository()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
