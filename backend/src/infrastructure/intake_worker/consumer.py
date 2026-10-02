import json
import logging
from uuid import UUID

import pika

from infrastructure.adapters.output.queue.intake_queue_topology import QUEUE_NAME, declare_intake_topology
from infrastructure.di.container import Container
from infrastructure.intake_worker.messages import process_job_message

_LOGGER = logging.getLogger(__name__)


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


def consume(container: Container, url: str) -> None:
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
