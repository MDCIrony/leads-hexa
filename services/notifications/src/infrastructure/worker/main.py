import logging
import signal
import threading

from chassis.consumer import ConsumerLoop, dlq_topic, ensure_topics_until_ready, run_consumer_lane
from chassis.kafka_config import consumer_config, producer_config
from chassis.web import configure_logging
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient

from infrastructure.adapters.input.consumers.groups import CONSUMER_GROUPS, DLQ_TOPIC_SPECS, handler_for
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container

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
    )


def main() -> int:
    settings = Settings.from_environment()
    configure_logging(settings.log_level)
    container = Container(settings)
    bootstrap = settings.kafka_bootstrap_servers
    stop, ready = threading.Event(), threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    # Only the dead-letter topics are declared here; the topics read belong to their producers.
    threads = [
        threading.Thread(
            target=ensure_topics_until_ready,
            args=(AdminClient({"bootstrap.servers": bootstrap}), DLQ_TOPIC_SPECS, stop, ready.set),
            name="ensure-topics", daemon=True,
        ),
        *(
            threading.Thread(
                target=run_consumer_lane,
                args=(group, lambda group=group, topic=topic: _consumer_loop(container, bootstrap, group, topic),
                      ready, stop),
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
