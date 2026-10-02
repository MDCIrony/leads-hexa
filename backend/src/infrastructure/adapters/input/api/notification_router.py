from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.commands import MarkNotificationReadCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetNotificationsQuery
from application.ports.input.notification_use_case_ports import (
    GetNotificationsInputPort, MarkAllNotificationsReadInputPort, MarkNotificationReadInputPort,
)
from domain.entities.notification import Notification
from infrastructure.adapters.input.api.dependencies import (
    get_get_notifications_use_case, get_mark_all_notifications_read_use_case,
    get_mark_notification_read_use_case, require_organization_member,
)
from infrastructure.adapters.input.api.schemas import NotificationResponse, NotificationsPageResponse

router = APIRouter()


def _to_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=str(notification.id),
        kind=notification.kind.value,
        message=notification.message,
        lead_id=str(notification.lead_id) if notification.lead_id else None,
        intake_record_id=str(notification.intake_record_id) if notification.intake_record_id else None,
        is_read=notification.is_read,
        created_at=notification.created_at,
    )


@router.get("", response_model=NotificationsPageResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=NotificationsPageResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetNotificationsInputPort = Depends(get_get_notifications_use_case),
    context: RequestContext = Depends(require_organization_member),
):
    query = GetNotificationsQuery(
        recipient_id=context.principal.id, unread_only=unread_only, limit=limit, offset=offset
    )
    page = use_case.execute(query)
    items = [_to_response(notification) for notification in page.items]
    return NotificationsPageResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
        unread_count=page.unread_count,
    )


# Declared before /{notification_id}/read: FastAPI resolves routes in
# declaration order, so "read-all" would otherwise be swallowed by the
# parametric route and rejected as an invalid UUID.
@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    use_case: MarkAllNotificationsReadInputPort = Depends(get_mark_all_notifications_read_use_case),
    context: RequestContext = Depends(require_organization_member),
):
    use_case.execute(context.principal.id)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: UUID,
    use_case: MarkNotificationReadInputPort = Depends(get_mark_notification_read_use_case),
    context: RequestContext = Depends(require_organization_member),
):
    command = MarkNotificationReadCommand(
        recipient_id=context.principal.id, notification_id=notification_id
    )
    use_case.execute(command)
