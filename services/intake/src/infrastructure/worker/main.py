import logging
import signal
import threading

import psycopg
from chassis.consumer import ConsumerLoop, dlq_topic, ensure_topics_until_ready, run_consumer_lane
from chassis.kafka_config import consumer_config, producer_config
from chassis.outbox import KafkaEventDispatcher, run_relay
from chassis.rabbit import RabbitJobDispatcher
from chassis.web import configure_logging
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient

from infrastructure.adapters.input.consumers.groups import CONSUMER_GROUPS, DLQ_TOPIC_SPECS, handler_for
from infrastructure.adapters.output.events.internal_topics import INTERNAL_TOPIC_SPECS, topic_for
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.adapters.output.queue.job_message import job_message
from infrastructure.adapters.output.queue.topology import QUEUE_NAME, declare_intake_topology
from infrastructure.config.settings import WorkerSettings
from infrastructure.di.container import Container
from infrastructure.worker.jobs import process_job_message
from infrastructure.worker.rabbit_lane import run_job_consumer
from infrastructure.worker.relays import build_dispatchers, build_relays

_LOGGER = logging.getLogger(__name__)

# Written into every envelope; consumers do not filter on it, but it says who emitted the fact.
PRODUCER_NAME = "intake"

_JOIN_TIMEOUT_SECONDS = 15.0


def _consumer_loop(container: Container, bootstrap: str, group: str, topic: str) -> ConsumerLoop:
    _LOGGER.info("Consumer group %s subscribing to %s (dead letters: %s)", group, topic, dlq_topic(group))
    return ConsumerLoop(
        Consumer(consumer_config(bootstrap, group)),
        Producer(producer_config(bootstrap, auto_create_topics=False)),
        group,
        [topic],
        handler_for(group, container.unit_of_work),
        # A database outage is waited out: dead-lettering a tenant state would
        # leave the organization without its default sources, silently and for good.
        retryable=lambda exc: isinstance(exc, psycopg.OperationalError),
    )


def _lanes(container: Container, settings: WorkerSettings, stop: threading.Event) -> list[threading.Thread]:
    bootstrap = settings.kafka_bootstrap_servers
    consumers_ready = threading.Event()
    dispatchers = build_dispatchers(
        RabbitJobDispatcher(settings.rabbitmq_url, QUEUE_NAME, declare_intake_topology, job_message),
    )
    internal_dispatcher = KafkaEventDispatcher(
        Producer(producer_config(bootstrap, auto_create_topics=False)), PRODUCER_NAME, topic_for,
    )
    relays = build_relays(lambda: open_outbox_store(container.database), dispatchers)
    admin = AdminClient({"bootstrap.servers": bootstrap})
    return [
        *(
            threading.Thread(
                target=run_relay, args=(relay, stop, settings.outbox_relay_interval_seconds),
                name=f"relay-{channel}", daemon=True,
            )
            for channel, relay in relays.items()
        ),
        threading.Thread(
            target=ensure_topics_until_ready,
            args=(admin, INTERNAL_TOPIC_SPECS, stop, lambda: dispatchers["internal"].append(internal_dispatcher)),
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


def main() -> int:
    settings = WorkerSettings.from_environment()
    configure_logging(settings.log_level)
    container = Container(settings)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    threads = _lanes(container, settings, stop)
    for thread in threads:
        thread.start()
        _LOGGER.info("Lane %s started", thread.name)

    # On the main thread: it owns the RabbitMQ connection and pumps its events
    # (heartbeats included) while each job runs on a thread of its own.
    run_job_consumer(settings.rabbitmq_url, lambda message: process_job_message(container, message), stop)
    _LOGGER.info("Stopping")
    for thread in threads:
        thread.join(timeout=_JOIN_TIMEOUT_SECONDS)
    container.close()
    return 0
