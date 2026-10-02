import logging
import signal
import threading

from chassis.consumer import ensure_topics_until_ready
from chassis.kafka_config import producer_config
from chassis.outbox import KafkaEventDispatcher, OutboxRelay, run_relay
from chassis.persistence import RawSqlDatabase
from chassis.web import configure_logging
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient

from infrastructure.adapters.output.events.internal_topics import INTERNAL_TOPIC_SPECS, topic_for
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.config.settings import WorkerSettings

_LOGGER = logging.getLogger(__name__)

# Written into every envelope; consumers do not filter on it, but it says who emitted the fact.
PRODUCER_NAME = "identity"

_JOIN_TIMEOUT_SECONDS = 15.0


def run(settings: WorkerSettings, stop: threading.Event) -> None:
    """Relays the `internal` channel until `stop` is set."""
    database = RawSqlDatabase(settings.database_url)
    bootstrap = settings.kafka_bootstrap_servers
    # Empty until the topics exist: the relay skips a channel with no dispatcher, so
    # rows wait instead of reaching a topic Kafka would auto-create without compaction.
    internal_dispatchers: list = []
    relay = OutboxRelay(lambda: open_outbox_store(database), {"internal": internal_dispatchers})
    dispatcher = KafkaEventDispatcher(
        Producer(producer_config(bootstrap, auto_create_topics=False)), PRODUCER_NAME, topic_for,
    )
    threads = [
        threading.Thread(
            target=run_relay, args=(relay, stop, settings.outbox_relay_interval_seconds),
            name="relay-internal", daemon=True,
        ),
        threading.Thread(
            target=ensure_topics_until_ready,
            args=(AdminClient({"bootstrap.servers": bootstrap}), INTERNAL_TOPIC_SPECS, stop,
                  lambda: internal_dispatchers.append(dispatcher)),
            name="ensure-topics", daemon=True,
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
    database.close()


def main() -> int:
    settings = WorkerSettings.from_environment()
    configure_logging(settings.log_level)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    run(settings, stop)
    return 0
