from typing import Any, List, Optional
from uuid import UUID

import psycopg

from application.ports.output.notification_repository_port import NotificationRepositoryPort
from domain.entities.notification import Notification


class RawSqlNotificationRepository(NotificationRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, notification: Notification) -> Notification:
        # Every field but is_read is fixed at creation (N2): the upsert exists
        # so mark_as_read has something to persist through, not to let the
        # rest of the row drift.
        self.connection.execute(
            """
            INSERT INTO notifications (
                id, tenant_id, recipient_id, kind, lead_id, intake_record_id,
                message, is_read, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                is_read = EXCLUDED.is_read
            """,
            (
                notification.id.value,
                notification.tenant_id.value,
                notification.recipient_id.value,
                notification.kind.value,
                notification.lead_id.value if notification.lead_id else None,
                notification.intake_record_id.value if notification.intake_record_id else None,
                notification.message,
                notification.is_read,
                notification.created_at,
            ),
        )
        return notification

    def get_by_id_and_recipient(self, notification_id: UUID, recipient_id: UUID) -> Optional[Notification]:
        row = self.connection.execute(
            "SELECT * FROM notifications WHERE id = %s AND recipient_id = %s",
            (notification_id, recipient_id),
        ).fetchone()
        return self._row_to_notification(row) if row else None

    def list_by_recipient(
        self,
        recipient_id: UUID,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        # The f-string composes only fixed column names written in this file;
        # every value still travels through a %s marker (C3).
        clauses = ["recipient_id = %s"]
        params: List[Any] = [recipient_id]
        if unread_only:
            clauses.append("is_read = FALSE")
        rows = self.connection.execute(
            f"SELECT * FROM notifications WHERE {' AND '.join(clauses)}"
            " ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
            (*params, limit, offset),
        ).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int:
        clauses = ["recipient_id = %s"]
        params: List[Any] = [recipient_id]
        if unread_only:
            clauses.append("is_read = FALSE")
        row = self.connection.execute(
            f"SELECT COUNT(*) AS count FROM notifications WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
        return row["count"]

    def mark_all_read(self, recipient_id: UUID) -> int:
        # A single UPDATE and its rowcount: walking every row to mark it
        # individually would be N queries to produce one number.
        cursor = self.connection.execute(
            "UPDATE notifications SET is_read = TRUE WHERE recipient_id = %s AND is_read = FALSE",
            (recipient_id,),
        )
        return cursor.rowcount

    @staticmethod
    def _row_to_notification(row) -> Notification:
        return Notification.create(
            notification_id=row["id"],
            tenant_id=row["tenant_id"],
            recipient_id=row["recipient_id"],
            kind=row["kind"],
            message=row["message"],
            lead_id=row["lead_id"],
            intake_record_id=row["intake_record_id"],
            is_read=row["is_read"],
            created_at=row["created_at"],
        )
