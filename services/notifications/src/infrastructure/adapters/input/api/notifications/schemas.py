from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    kind: str
    message: str
    lead_id: str | None = None
    intake_record_id: str | None = None
    is_read: bool
    created_at: datetime


class NotificationsPageResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    # Travels with the page rather than in its own endpoint: the bell needs
    # the list and the badge at once, and two requests to paint one icon is
    # what turns polling into a problem.
    unread_count: int
