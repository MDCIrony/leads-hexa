from application.dtos.notifications import GetNotificationsQuery, NotificationsPageResult
from application.ports.input.notifications import GetNotificationsInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort


class GetNotificationsUseCase(GetNotificationsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetNotificationsQuery) -> NotificationsPageResult:
        with self.uow:
            items = self.uow.notifications.list_by_recipient(
                query.recipient_id, unread_only=query.unread_only, limit=query.limit, offset=query.offset
            )
            total = self.uow.notifications.count_by_recipient(query.recipient_id, unread_only=query.unread_only)
            # Always the recipient's full unread count, never the page's: the
            # bell shows one number and it must not change with pagination.
            unread = self.uow.notifications.count_by_recipient(query.recipient_id, unread_only=True)
        return NotificationsPageResult(items=items, total=total, unread_count=unread)
