"""Delivery process: relays the outbox to Kafka and webhooks, and runs the notification consumers.

Its own compose service, not threads inside the API, so a slow broker or a
webhook that times out can never take request capacity with it, and the API can
restart without interrupting delivery. Run with `python -m infrastructure.worker`."""

import logging
import signal
import threading
from typing import Callable, Sequence

from chassis.consumer import ConsumerLoop, TopicSpec, dlq_topic, ensure_topics
from chassis.outbox import Dispatcher, KafkaEventDispatcher, OutboxRelay, run_relay
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient

from application.ports.output.webhook_repository_port import WebhookRepositoryPort
from domain.entities.webhook import WebhookConfig
from domain.value_objects.enums import WebhookEventType
from infrastructure.adapters.input.events.notification_consumer import NotificationConsumer
from infrastructure.adapters.output.events.internal_topics import (
    INTERNAL_TOPIC_SPECS,
    NOTIFICATION_GROUPS,
    topic_for,
)
from infrastructure.adapters.output.events.kafka_outbound_dispatcher import KafkaOutboundDispatcher
from infrastructure.adapters.output.events.webhook_outbound_dispatcher import WebhookOutboundDispatcher
from infrastructure.adapters.output.http.httpx_webhook_dispatcher import HttpxWebhookDispatcher
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.adapters.output.persistence.raw_sql_webhook_repository import RawSqlWebhookRepository
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from infrastructure.logging_config import configure_logging

_LOGGER = logging.getLogger(__name__)

# What every service of this platform that publishes calls itself; in F1 only
# the monolith writes, so this process publishes on its behalf.
_PRODUCER_NAME = "lead-core"
_JOIN_TIMEOUT_SECONDS = 15.0
_ENSURE_MAX_BACKOFF_SECONDS = 30.0


class _PooledWebhookRepository(WebhookRepositoryPort):
    """Borrows a connection per lookup instead of pinning one for the process lifetime.

    A pinned connection that the database drops would fail every webhook
    lookup until the container restarts; a borrowed one is replaced by the pool."""

    def __init__(self, database: RawSqlDatabase) -> None:
        self._database = database

    def get_by_tenant_and_event(self, tenant_id: str, event_type: WebhookEventType) -> list[WebhookConfig]:
        with self._database.get_connection(autocommit=True) as connection:
            return RawSqlWebhookRepository(connection).get_by_tenant_and_event(tenant_id, event_type)


def producer_config(bootstrap_servers: str) -> dict:
    return {
        "bootstrap.servers": bootstrap_servers,
        "acks": "all",
        "enable.idempotence": True,
        # Matches the dispatchers' flush timeout: a message the producer is
        # still retrying must not be delivered after its row was marked failed.
        "message.timeout.ms": 10_000,
    }


def build_dispatchers(product: Sequence[Dispatcher]) -> dict[str, list[Dispatcher]]:
    """Dispatchers by outbox channel.

    `internal` starts empty and is filled once its topics exist: the relay skips
    a channel with no dispatcher, so rows wait instead of reaching a topic that
    Kafka would auto-create without compaction. `job` stays empty until the job
    channel is wired (task 4b)."""
    return {"product": list(product), "internal": [], "job": []}


def ensure_topics_until_ready(
    admin,
    specs: Sequence[TopicSpec],
    stop: threading.Event,
    on_ready: Callable[[], None],
) -> bool:
    """Retries with backoff until the topics exist; returns False if stopped first.

    A broker that is down must not take the process with it (ADR-0026): the
    product relay keeps running meanwhile."""
    delay = 1.0
    while not stop.is_set():
        try:
            ensure_topics(admin, specs)
        except Exception:
            _LOGGER.warning("Kafka topics not ready, retrying in %.0fs", delay, exc_info=True)
            if stop.wait(delay):
                return False
            delay = min(delay * 2, _ENSURE_MAX_BACKOFF_SECONDS)
        else:
            _LOGGER.info("Kafka topics ensured: %s", ", ".join(spec.name for spec in specs))
            on_ready()
            return True
    return False


def _run_consumer(
    container: Container, bootstrap_servers: str, group: str, topic: str,
    ready: threading.Event, stop: threading.Event,
) -> None:
    # Subscribing earlier would let a group join and read a topic that Kafka
    # auto-created with the wrong configuration.
    while not ready.wait(0.5):
        if stop.is_set():
            return
    consumer = Consumer({
        "bootstrap.servers": bootstrap_servers,
        "group.id": group,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    loop = ConsumerLoop(
        consumer,
        Producer(producer_config(bootstrap_servers)),
        group,
        [topic],
        NotificationConsumer(container.unit_of_work, group),
    )
    _LOGGER.info("Consumer group %s subscribing to %s (dead letters: %s)", group, topic, dlq_topic(group))
    loop.run(stop)


def _guarded(name: str, target: Callable[[], None], stop: threading.Event, failed: threading.Event) -> threading.Thread:
    def run() -> None:
        try:
            target()
        except Exception:
            # Nothing restarts a dead thread: take the process down so the
            # supervisor does, instead of running on with a lane silently gone.
            _LOGGER.error("Worker thread %s died", name, exc_info=True)
            failed.set()
            stop.set()

    return threading.Thread(target=run, name=name, daemon=True)


def main() -> int:
    configure_logging()
    settings = Settings.from_environment()
    container = Container(settings)
    bootstrap = settings.kafka_bootstrap_servers
    stop, failed, ready = threading.Event(), threading.Event(), threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    product_dispatchers = [
        WebhookOutboundDispatcher(
            webhook_repo=_PooledWebhookRepository(container.database),
            webhook_dispatcher=HttpxWebhookDispatcher(timeout=settings.webhook_timeout_seconds),
        ),
        KafkaOutboundDispatcher(producer=Producer(producer_config(bootstrap))),
    ]
    dispatchers = build_dispatchers(product_dispatchers)
    internal_dispatcher = KafkaEventDispatcher(
        Producer(producer_config(bootstrap)), _PRODUCER_NAME, topic_for,
    )

    def activate_internal() -> None:
        dispatchers["internal"].append(internal_dispatcher)
        ready.set()

    relay = OutboxRelay(lambda: open_outbox_store(container.database), dispatchers)
    specs = [*INTERNAL_TOPIC_SPECS]
    threads = [
        _guarded(
            "outbox-relay",
            lambda: run_relay(relay, stop, settings.outbox_relay_interval_seconds),
            stop, failed,
        ),
        _guarded(
            "ensure-topics",
            lambda: ensure_topics_until_ready(AdminClient({"bootstrap.servers": bootstrap}), specs, stop, activate_internal),
            stop, failed,
        ),
        *(
            _guarded(
                f"consumer-{group}",
                lambda group=group, topic=topic: _run_consumer(container, bootstrap, group, topic, ready, stop),
                stop, failed,
            )
            for group, topic in NOTIFICATION_GROUPS.items()
        ),
    ]
    for thread in threads:
        thread.start()
    _LOGGER.info("Outbox relay running (channels: %s)", ", ".join(dispatchers))

    while not stop.wait(1.0):
        pass
    _LOGGER.info("Stopping")
    for thread in threads:
        thread.join(timeout=_JOIN_TIMEOUT_SECONDS)
    container.database.close()
    return 1 if failed.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
