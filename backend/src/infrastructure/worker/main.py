import logging
import signal
import threading

import psycopg
from chassis.consumer import ConsumerLoop, dlq_topic, ensure_topics_until_ready, run_consumer_lane
from chassis.kafka_config import consumer_config, producer_config
from chassis.outbox import KafkaEventDispatcher, run_relay
from chassis.rabbit import RabbitJobDispatcher
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient

from infrastructure.adapters.input.consumers.groups import CONSUMER_GROUPS, DLQ_TOPIC_SPECS, handler_for
from infrastructure.adapters.output.events.internal_topics import INTERNAL_TOPIC_SPECS, topic_for
from infrastructure.adapters.output.events.kafka_outbound_dispatcher import KafkaOutboundDispatcher
from infrastructure.adapters.output.events.webhook_outbound_dispatcher import WebhookOutboundDispatcher
from infrastructure.adapters.output.http.httpx_webhook_dispatcher import HttpxWebhookDispatcher
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.adapters.output.persistence.raw_sql_webhook_repository import PooledWebhookRepository
from infrastructure.adapters.output.queue.intake_queue_topology import QUEUE_NAME, declare_intake_topology
from infrastructure.adapters.output.queue.job_message import job_message
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from infrastructure.logging_config import configure_logging
from infrastructure.worker.producers import PRODUCER_NAME
from infrastructure.worker.relays import build_dispatchers, build_relays

_LOGGER = logging.getLogger(__name__)

_JOIN_TIMEOUT_SECONDS = 15.0


def _consumer_loop(container: Container, bootstrap: str, group: str, topic: str) -> ConsumerLoop:
    _LOGGER.info("Consumer group %s subscribing to %s (dead letters: %s)", group, topic, dlq_topic(group))
    return ConsumerLoop(
        Consumer(consumer_config(bootstrap, group)),
        Producer(producer_config(bootstrap, auto_create_topics=False)),
        group,
        [topic],
        handler_for(group, container.unit_of_work),
        # A database outage is waited out: dead-lettering a state event would
        # leave the advisors projection diverged, or a tenant without its
        # default sources, silently and for good.
        retryable=lambda exc: isinstance(exc, psycopg.OperationalError),
    )


def main() -> int:
    configure_logging()
    settings = Settings.from_environment()
    container = Container(settings)
    bootstrap = settings.kafka_bootstrap_servers
    stop, consumers_ready = threading.Event(), threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    product_dispatchers = [
        WebhookOutboundDispatcher(
            webhook_repo=PooledWebhookRepository(container.database),
            webhook_dispatcher=HttpxWebhookDispatcher(timeout=settings.webhook_timeout_seconds),
        ),
        KafkaOutboundDispatcher(producer=Producer(producer_config(bootstrap))),
    ]
    dispatchers = build_dispatchers(
        product_dispatchers,
        [RabbitJobDispatcher(settings.rabbitmq_url, QUEUE_NAME, declare_intake_topology, job_message)],
    )
    internal_dispatcher = KafkaEventDispatcher(
        Producer(producer_config(bootstrap, auto_create_topics=False)), PRODUCER_NAME, topic_for,
    )

    def activate_internal() -> None:
        dispatchers["internal"].append(internal_dispatcher)

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
        # Consumers wait only for their own dead-letter topics; the topics they
        # read belong to their producers.
        threading.Thread(
            target=ensure_topics_until_ready,
            args=(admin, DLQ_TOPIC_SPECS, stop, consumers_ready.set),
            name="ensure-dlq-topics", daemon=True,
        ),
        *(
            threading.Thread(
                target=run_consumer_lane,
                args=(group, lambda group=group, topic=topic: _consumer_loop(container, bootstrap, group, topic),
                      consumers_ready, stop),
                name=f"consumer-{group}", daemon=True,
            )
            for group, topic in CONSUMER_GROUPS.items()
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
