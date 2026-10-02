import logging
import threading
import time
from typing import Callable, Sequence

from chassis.consumer import ConsumerLoop, TopicSpec, dlq_topic, ensure_topics
from confluent_kafka import Consumer, Producer

from infrastructure.adapters.input.events.notification_consumer import NotificationConsumer
from infrastructure.di.container import Container
from infrastructure.worker.config import producer_config

_LOGGER = logging.getLogger(__name__)

_MAX_BACKOFF_SECONDS = 30.0


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


def consumer_loop(container: Container, bootstrap_servers: str, group: str, topic: str) -> ConsumerLoop:
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
