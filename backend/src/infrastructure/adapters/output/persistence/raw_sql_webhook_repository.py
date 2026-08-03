import sqlite3
from typing import List
from application.ports.output.webhook_repository_port import WebhookRepositoryPort
from domain.entities.webhook import WebhookConfig
from domain.value_objects.enums import WebhookEventType


class RawSqlWebhookRepository(WebhookRepositoryPort):
    """Raw SQL implementation of WebhookRepositoryPort using SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_by_tenant_and_event(
        self, tenant_id: str, event_type: WebhookEventType
    ) -> List[WebhookConfig]:
        cursor = self.connection.cursor()
        event_val = event_type.value if hasattr(event_type, "value") else str(event_type)
        cursor.execute(
            """
            SELECT id, tenant_id, event_type, target_url, secret_token
            FROM webhook_configs
            WHERE tenant_id = ? AND event_type = ?
            """,
            (tenant_id, event_val),
        )
        rows = cursor.fetchall()
        configs = []
        for row in rows:
            configs.append(
                WebhookConfig.create(
                    config_id=row[0],
                    tenant_id=row[1],
                    event_type=row[2],
                    target_url=row[3],
                    secret_token=row[4],
                )
            )
        return configs
