import json
import logging
from uuid import UUID

import pika

from application.ports.output.job_queue_port import JobQueuePort

_LOGGER = logging.getLogger(__name__)

QUEUE_NAME = "intake.jobs"
DLQ_NAME = "intake.jobs.dlq"

# A quorum queue is what makes the count native: RabbitMQ dead-letters a
# message itself once its own delivery counter passes this, instead of the
# application tracking attempts through the x-death header by hand.
_MAX_DELIVERIES = 3


def declare_intake_topology(channel) -> None:
    """Declared identically by the producer and the worker: RabbitMQ rejects a
    redeclare of the same queue with mismatched arguments."""
    channel.queue_declare(queue=DLQ_NAME, durable=True)
    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": _MAX_DELIVERIES,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": DLQ_NAME,
        },
    )


class RabbitMQJobQueue(JobQueuePort):
    """Opens one short-lived connection per call instead of holding one open:
    FastAPI runs sync endpoints in a thread pool, and pika's BlockingConnection
    is not safe to share across threads."""

    def __init__(self, url: str) -> None:
        self._url = url

    def enqueue_intake_job(self, tenant_id: UUID, job_id: UUID) -> bool:
        body = json.dumps({"tenant_id": str(tenant_id), "job_id": str(job_id)}).encode()
        try:
            with pika.BlockingConnection(pika.URLParameters(self._url)) as connection:
                channel = connection.channel()
                declare_intake_topology(channel)
                channel.basic_publish(
                    exchange="",
                    routing_key=QUEUE_NAME,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )
            return True
        except pika.exceptions.AMQPError:
            _LOGGER.warning("RabbitMQ unreachable, caller must fall back", exc_info=True)
            return False
