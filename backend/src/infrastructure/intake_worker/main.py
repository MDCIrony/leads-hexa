import logging
import time

from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from infrastructure.intake_worker.consumer import consume
from infrastructure.logging_config import configure_logging

_LOGGER = logging.getLogger(__name__)
_MAX_BACKOFF_SECONDS = 30.0


def main() -> None:
    configure_logging()
    settings = Settings.from_environment()
    container = Container(settings)

    # Reconnects in process instead of exiting: under the dev file watcher an
    # exited worker stays down until a file changes, and the jobs the relay
    # keeps publishing would wait for nobody.
    delay = 1.0
    while True:
        started = time.monotonic()
        try:
            consume(container, settings.rabbitmq_url)
        # OSError too: a broker host that does not resolve surfaces as
        # socket.gaierror, which pika re-raises unwrapped.
        except (AMQPConnectionError, ChannelClosedByBroker, OSError) as exc:
            if time.monotonic() - started > _MAX_BACKOFF_SECONDS:
                delay = 1.0
            _LOGGER.warning("RabbitMQ unavailable (%r), reconnecting in %.0fs", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, _MAX_BACKOFF_SECONDS)
