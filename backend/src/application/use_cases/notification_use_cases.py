from uuid import UUID

from application.dtos.commands import MarkNotificationReadCommand, NotificationsPageResult
from application.dtos.queries import GetNotificationsQuery
from application.ports.input.notification_use_case_ports import (
    GetNotificationsInputPort,
    MarkAllNotificationsReadInputPort,
    MarkNotificationReadInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.notification import Notification
from domain.exceptions import DomainException


def _get_own_notification(uow: UnitOfWorkPort, recipient_id: UUID, notification_id: UUID) -> Notification:
    """A notice belonging to another recipient must read back as missing."""
    notification = uow.notifications.get_by_id_and_recipient(notification_id, recipient_id)
    if notification is None:
        raise DomainException("La notificación no existe", error_code="NOTIFICATION_NOT_FOUND")
    return notification


class GetNotificationsUseCase(GetNotificationsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetNotificationsQuery) -> NotificationsPageResult:
        with self.uow:
            items = self.uow.notifications.list_by_recipient(
                query.recipient_id,
                unread_only=query.unread_only,
                limit=query.limit,
                offset=query.offset,
            )
            total = self.uow.notifications.count_by_recipient(
                query.recipient_id, unread_only=query.unread_only
            )
            # Always the recipient's full unread count, never the page's: the
            # bell shows one number and it must not change with pagination.
            unread = self.uow.notifications.count_by_recipient(
                query.recipient_id, unread_only=True
            )
        return NotificationsPageResult(items=items, total=total, unread_count=unread)


class MarkNotificationReadUseCase(MarkNotificationReadInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: MarkNotificationReadCommand) -> None:
        with self.uow:
            notification = _get_own_notification(self.uow, command.recipient_id, command.notification_id)
            notification.mark_as_read()
            self.uow.notifications.save(notification)


class MarkAllNotificationsReadUseCase(MarkAllNotificationsReadInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, recipient_id: UUID) -> int:
        with self.uow:
            return self.uow.notifications.mark_all_read(recipient_id)
