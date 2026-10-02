from typing import Callable, Sequence

from chassis.outbox import Dispatcher, OutboxRelay

from application.ports.output.webhook_repository_port import WebhookRepositoryPort
from domain.entities.webhook import WebhookConfig
from domain.value_objects.enums import WebhookEventType
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.raw_sql_webhook_repository import RawSqlWebhookRepository


class PooledWebhookRepository(WebhookRepositoryPort):
    """Borrows a connection per lookup instead of pinning one for the process lifetime.

    A pinned connection that the database drops would fail every webhook
    lookup until the container restarts; a borrowed one is replaced by the pool."""

    def __init__(self, database: RawSqlDatabase) -> None:
        self._database = database

    def get_by_tenant_and_event(self, tenant_id: str, event_type: WebhookEventType) -> list[WebhookConfig]:
        with self._database.get_connection(autocommit=True) as connection:
            return RawSqlWebhookRepository(connection).get_by_tenant_and_event(tenant_id, event_type)


def build_dispatchers(
    product: Sequence[Dispatcher], job: Sequence[Dispatcher],
) -> dict[str, list[Dispatcher]]:
    """Dispatchers by outbox channel.

    `internal` starts empty and is filled once its topics exist: the relay skips
    a channel with no dispatcher, so rows wait instead of reaching a topic that
    Kafka would auto-create without compaction."""
    return {"product": list(product), "internal": [], "job": list(job)}


def build_relays(
    store: Callable, dispatchers: dict[str, list[Dispatcher]],
) -> dict[str, OutboxRelay]:
    """One relay per channel, each on its own thread.

    Delivery is sequential inside a relay, so a shared one would let an
    unreachable Kafka on `internal` hold up the `product` webhooks behind it.
    Each gets the channel's own list, which keeps the late activation of
    `internal` visible to its relay."""
    return {channel: OutboxRelay(store, {channel: lanes}) for channel, lanes in dispatchers.items()}
