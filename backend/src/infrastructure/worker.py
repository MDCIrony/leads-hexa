"""Delivery process: relays the outbox to Kafka and webhooks, and runs the notification consumers.

Its own compose service, not threads inside the API, so a slow broker or a
webhook that times out can never take request capacity with it, and the API can
restart without interrupting delivery. Run with `python -m infrastructure.worker`."""

import logging
import signal
import threading
import time
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
_MAX_BACKOFF_SECONDS = 30.0


class _PooledWebhookRepository(WebhookRepositoryPort):
    """Borrows a connection per lookup instead of pinning one for the process lifetime.

    A pinned connection that the database drops would fail every webhook
    lookup until the container restarts; a borrowed one is replaced by the pool."""

    def __init__(self, database: RawSqlDatabase) -> None:
        self._database = database

    def get_by_tenant_and_event(self, tenant_id: str, event_type: WebhookEventType) -> list[WebhookConfig]:
        with self._database.get_connection(autocommit=True) as connection:
            return RawSqlWebhookRepository(connection).get_by_tenant_and_event(tenant_id, event_type)


def producer_config(bootstrap_servers: str, auto_create_topics: bool = True) -> dict:
    config = {
        "bootstrap.servers": bootstrap_servers,
        "acks": "all",
        "enable.idempotence": True,
        # Strictly below the dispatchers' 10 s flush: a message the producer is
        # still retrying when flush gives up must not be delivered after its
        # row was marked failed.
        "message.timeout.ms": 9_000,
    }
    if not auto_create_topics:
        # Internal topics are created by ensure_topics with their retention and
        # compaction; a topic lost later must fail loudly, not come back
        # uncompacted through broker auto-creation.
        config["allow.auto.create.topics"] = False
    return config


def build_dispatchers(product: Sequence[Dispatcher]) -> dict[str, list[Dispatcher]]:
    """Dispatchers by outbox channel.

    `internal` starts empty and is filled once its topics exist: the relay skips
    a channel with no dispatcher, so rows wait instead of reaching a topic that
    Kafka would auto-create without compaction. `job` stays empty until the job
    channel is wired (task 4b)."""
    return {"product": list(product), "internal": [], "job": []}


def build_relays(
    store: Callable, dispatchers: dict[str, list[Dispatcher]],
) -> dict[str, OutboxRelay]:
    """One relay per channel, each on its own thread.

    Delivery is sequential inside a relay, so a shared one would let an
    unreachable Kafka on `internal` hold up the `product` webhooks behind it.
    Each gets the channel's own list, which keeps the late activation of
    `internal` visible to its relay."""
    return {channel: OutboxRelay(store, {channel: lanes}) for channel, lanes in dispatchers.items()}


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
        except Exception as exc:
            _LOGGER.warning("Kafka topics not ready (%s), retrying in %.0fs", exc, delay)
            _LOGGER.debug("Kafka topics not ready", exc_info=True)
            if stop.wait(delay):
                return False
            delay = min(delay * 2, _MAX_BACKOFF_SECONDS)
        else:
            _LOGGER.info("Kafka topics ensured: %s", ", ".join(spec.name for spec in specs))
            on_ready()
            return True
    return False


def run_consumer_lane(
    name: str, build_loop: Callable[[], ConsumerLoop],
    ready: threading.Event, stop: threading.Event,
) -> None:
    """Builds a consumer and runs it; on any failure builds a new one after a capped backoff.

    A fatal Kafka error or a failed subscribe ends one consumer, not the lane:
    nothing restarts a dead thread, and under the dev file watcher a crashed
    process stays up doing nothing. Only `stop` ends this."""
    # Subscribing earlier would let a group join and read a topic that Kafka
    # auto-created with the wrong configuration.
    while not ready.wait(0.5):
        if stop.is_set():
            return
    delay = 1.0
    while not stop.is_set():
        started = time.monotonic()
        try:
            build_loop().run(stop)
        except Exception as exc:
            _LOGGER.warning("Consumer lane %s failed (%s), retrying in %.0fs", name, exc, delay)
            _LOGGER.debug("Consumer lane %s failed", name, exc_info=True)
            # A consumer that ran for a while before failing is a new incident,
            # not a continuation of the last one.
            if time.monotonic() - started > _MAX_BACKOFF_SECONDS:
                delay = 1.0
            if stop.wait(delay):
                return
            delay = min(delay * 2, _MAX_BACKOFF_SECONDS)


def _consumer_loop(container: Container, bootstrap_servers: str, group: str, topic: str) -> ConsumerLoop:
    consumer = Consumer({
        "bootstrap.servers": bootstrap_servers,
        "group.id": group,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    _LOGGER.info("Consumer group %s subscribing to %s (dead letters: %s)", group, topic, dlq_topic(group))
    return ConsumerLoop(
        consumer,
        Producer(producer_config(bootstrap_servers, auto_create_topics=False)),
        group,
        [topic],
        NotificationConsumer(container.unit_of_work, group),
    )


def main() -> int:
    configure_logging()
    settings = Settings.from_environment()
    container = Container(settings)
    bootstrap = settings.kafka_bootstrap_servers
    stop, ready = threading.Event(), threading.Event()
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
        Producer(producer_config(bootstrap, auto_create_topics=False)), _PRODUCER_NAME, topic_for,
    )

    def activate_internal() -> None:
        dispatchers["internal"].append(internal_dispatcher)
        ready.set()

    relays = build_relays(lambda: open_outbox_store(container.database), dispatchers)
    admin = AdminClient({"bootstrap.servers": bootstrap})
    threads = [
        *(
            threading.Thread(
                target=run_relay, args=(relay, stop, settings.outbox_relay_interval_seconds),
                name=f"relay-{channel}", daemon=True,
            )
            for channel, relay in relays.items()
        ),
        threading.Thread(
            target=ensure_topics_until_ready,
            args=(admin, [*INTERNAL_TOPIC_SPECS], stop, activate_internal),
            name="ensure-topics", daemon=True,
        ),
        *(
            threading.Thread(
                target=run_consumer_lane,
                args=(
                    group,
                    lambda group=group, topic=topic: _consumer_loop(container, bootstrap, group, topic),
                    ready, stop,
                ),
                name=f"consumer-{group}", daemon=True,
            )
            for group, topic in NOTIFICATION_GROUPS.items()
        ),
    ]
    for thread in threads:
        thread.start()
        _LOGGER.info("Lane %s started", thread.name)

    while not stop.wait(1.0):
        pass
    _LOGGER.info("Stopping")
    for thread in threads:
        thread.join(timeout=_JOIN_TIMEOUT_SECONDS)
    container.database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
