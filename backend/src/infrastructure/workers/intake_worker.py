"""Standalone consumer for `intake.jobs` (ADR-0027): its own compose service,
not a thread inside the API process, so a container restart mid-file does not
strand the job.

Redelivery is what makes this safe to kill at any point: nothing is acked
until the job's run returns, and a run only ever reads PENDING records back."""

import json
import logging
import time
from uuid import UUID

import pika
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

from infrastructure.adapters.output.queue.intake_queue_topology import QUEUE_NAME, declare_intake_topology
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from infrastructure.logging_config import configure_logging
from infrastructure.workers.job_messages import process_job_message

_LOGGER = logging.getLogger(__name__)
_MAX_BACKOFF_SECONDS = 30.0


def _decode(body: bytes) -> dict:
    message = json.loads(body)
    for key in ("tenant_id", "job_id"):
        UUID(message[key])
    return message


def _handle_message(container: Container, channel, method, body: bytes) -> None:
    try:
        message = _decode(body)
    except Exception as exc:
        # Anything raising here would escape start_consuming and end the
        # worker; no redelivery fixes a body that is not a job message, so it
        # goes straight to the dead-letter queue.
        _LOGGER.warning("Malformed intake job message dead-lettered: %r", exc)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
    if process_job_message(container, message) == "nack":
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    else:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def _consume(container: Container, url: str) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(url))
    try:
        channel = connection.channel()
        declare_intake_topology(channel)
        # One job at a time per worker: jobs are long (up to 10k records), and a
        # deep prefetch would let one worker hoard several while others sit idle.
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=QUEUE_NAME,
            on_message_callback=lambda ch, method, properties, body: _handle_message(container, ch, method, body),
            auto_ack=False,
        )
        _LOGGER.info("Intake worker consuming from %s", QUEUE_NAME)
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()


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
            _consume(container, settings.rabbitmq_url)
        # OSError too: a broker host that does not resolve surfaces as
        # socket.gaierror, which pika re-raises unwrapped.
        except (AMQPConnectionError, ChannelClosedByBroker, OSError) as exc:
            if time.monotonic() - started > _MAX_BACKOFF_SECONDS:
                delay = 1.0
            _LOGGER.warning("RabbitMQ unavailable (%r), reconnecting in %.0fs", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, _MAX_BACKOFF_SECONDS)


if __name__ == "__main__":
    main()
