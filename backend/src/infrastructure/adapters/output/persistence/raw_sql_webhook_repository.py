from typing import List

import psycopg
from chassis.persistence import RawSqlDatabase

from application.ports.output.webhooks.webhook_repository_port import WebhookRepositoryPort
from domain.webhooks.webhook import WebhookConfig
from domain.value_objects.enums import WebhookEventType


class RawSqlWebhookRepository(WebhookRepositoryPort):
    """Raw SQL implementation of WebhookRepositoryPort using Postgres."""

    def __init__(self, connection: psycopg.Connection) -> None:
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
            WHERE tenant_id = %s AND event_type = %s
            """,
            (tenant_id, event_val),
        )
        rows = cursor.fetchall()
        configs = []
        for row in rows:
            configs.append(
                WebhookConfig.create(
                    config_id=row["id"],
                    tenant_id=row["tenant_id"],
                    event_type=row["event_type"],
                    target_url=row["target_url"],
                    secret_token=row["secret_token"],
                )
            )
        return configs


class PooledWebhookRepository(WebhookRepositoryPort):
    """Borrows a connection per lookup instead of pinning one for the process lifetime.

    A pinned connection that the database drops would fail every webhook
    lookup until the container restarts; a borrowed one is replaced by the pool."""

    def __init__(self, database: RawSqlDatabase) -> None:
        self._database = database

    def get_by_tenant_and_event(self, tenant_id: str, event_type: WebhookEventType) -> list[WebhookConfig]:
        with self._database.get_connection(autocommit=True) as connection:
            return RawSqlWebhookRepository(connection).get_by_tenant_and_event(tenant_id, event_type)
