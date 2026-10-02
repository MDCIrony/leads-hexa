import uuid

import pytest

from application.dtos.notifications import GetNotificationsQuery, MarkNotificationReadCommand
from application.use_cases.notifications.list_notifications import GetNotificationsUseCase
from application.use_cases.notifications.mark_read import (
    MarkAllNotificationsReadUseCase,
    MarkNotificationReadUseCase,
)
from domain.exceptions import DomainException
from domain.notifications.kind import NotificationKind
from domain.notifications.notification import Notification
from tests.unit.application.fakes import InMemoryUnitOfWork


def _add(uow: InMemoryUnitOfWork, recipient_id, is_read: bool = False) -> Notification:
    return uow.notifications.save(Notification.create(
        tenant_id=uuid.uuid4(), recipient_id=recipient_id, kind=NotificationKind.LEAD_ASSIGNED,
        message="Tienes un lead nuevo asignado", is_read=is_read,
    ))


class TestGetNotifications:
    def test_returns_only_the_recipients_notices(self):
        uow, me = InMemoryUnitOfWork(), uuid.uuid4()
        mine = _add(uow, me)
        _add(uow, uuid.uuid4())

        result = GetNotificationsUseCase(uow).execute(GetNotificationsQuery(recipient_id=me))

        assert result.items == [mine]
        assert result.total == 1

    def test_unread_count_ignores_the_filter_and_the_page(self):
        uow, me = InMemoryUnitOfWork(), uuid.uuid4()
        _add(uow, me)
        _add(uow, me)
        _add(uow, me, is_read=True)

        result = GetNotificationsUseCase(uow).execute(
            GetNotificationsQuery(recipient_id=me, unread_only=False, limit=1, offset=0)
        )

        assert len(result.items) == 1
        assert result.total == 3
        assert result.unread_count == 2

    def test_unread_only_narrows_the_total_but_not_the_unread_count(self):
        uow, me = InMemoryUnitOfWork(), uuid.uuid4()
        _add(uow, me)
        _add(uow, me, is_read=True)

        result = GetNotificationsUseCase(uow).execute(GetNotificationsQuery(recipient_id=me, unread_only=True))

        assert result.total == 1
        assert result.unread_count == 1


class TestMarkNotificationRead:
    def test_marks_the_recipients_notice(self):
        uow, me = InMemoryUnitOfWork(), uuid.uuid4()
        notification = _add(uow, me)

        MarkNotificationReadUseCase(uow).execute(
            MarkNotificationReadCommand(recipient_id=me, notification_id=notification.id)
        )

        assert uow.notifications.get_by_id_and_recipient(notification.id, me).is_read is True

    def test_a_notice_of_someone_else_reads_as_missing(self):
        uow = InMemoryUnitOfWork()
        notification = _add(uow, uuid.uuid4())

        with pytest.raises(DomainException) as exc:
            MarkNotificationReadUseCase(uow).execute(
                MarkNotificationReadCommand(recipient_id=uuid.uuid4(), notification_id=notification.id)
            )

        assert exc.value.error_code == "NOTIFICATION_NOT_FOUND"
        assert notification.is_read is False


class TestMarkAllNotificationsRead:
    def test_marks_every_unread_notice_and_returns_how_many(self):
        uow, me = InMemoryUnitOfWork(), uuid.uuid4()
        _add(uow, me)
        _add(uow, me)
        _add(uow, me, is_read=True)
        other = _add(uow, uuid.uuid4())

        assert MarkAllNotificationsReadUseCase(uow).execute(me) == 2

        assert uow.notifications.count_by_recipient(me, unread_only=True) == 0
        assert other.is_read is False
