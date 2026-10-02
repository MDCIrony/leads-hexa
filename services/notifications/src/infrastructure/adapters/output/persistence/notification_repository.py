import psycopg
from uuid import UUID

from application.ports.output.notification_repository import NotificationRepositoryPort
from domain.notifications.notification import Notification


class PostgresNotificationRepository(NotificationRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, notification: Notification) -> Notification:
        # Every field but is_read is fixed at creation: the upsert exists so
        # mark_as_read has something to persist through, not to let the rest of the row drift.
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
                notification.id, notification.tenant_id, notification.recipient_id, notification.kind.value,
                notification.lead_id, notification.intake_record_id, notification.message,
                notification.is_read, notification.created_at,
            ),
        )
        return notification

    def get_by_id_and_recipient(self, notification_id: UUID, recipient_id: UUID) -> Notification | None:
        row = self.connection.execute(
            "SELECT * FROM notifications WHERE id = %s AND recipient_id = %s",
            (notification_id, recipient_id),
        ).fetchone()
        return self._to_notification(row) if row else None

    def list_by_recipient(
        self, recipient_id: UUID, unread_only: bool = False, limit: int = 100, offset: int = 0
    ) -> list[Notification]:
        # The f-string composes only a fixed fragment written in this file; every value travels through %s.
        rows = self.connection.execute(
            f"SELECT * FROM notifications WHERE recipient_id = %s{self._unread(unread_only)}"
            " ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
            (recipient_id, limit, offset),
        ).fetchall()
        return [self._to_notification(row) for row in rows]

    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int:
        row = self.connection.execute(
            f"SELECT COUNT(*) AS count FROM notifications WHERE recipient_id = %s{self._unread(unread_only)}",
            (recipient_id,),
        ).fetchone()
        return row["count"]

    def mark_all_read(self, recipient_id: UUID) -> int:
        # One UPDATE and its rowcount: marking each row individually would be N queries for one number.
        cursor = self.connection.execute(
            "UPDATE notifications SET is_read = TRUE WHERE recipient_id = %s AND is_read = FALSE",
            (recipient_id,),
        )
        return cursor.rowcount

    @staticmethod
    def _unread(unread_only: bool) -> str:
        return " AND is_read = FALSE" if unread_only else ""

    @staticmethod
    def _to_notification(row) -> Notification:
        return Notification.create(
            notification_id=row["id"], tenant_id=row["tenant_id"], recipient_id=row["recipient_id"],
            kind=row["kind"], message=row["message"], lead_id=row["lead_id"],
            intake_record_id=row["intake_record_id"], is_read=row["is_read"], created_at=row["created_at"],
        )
