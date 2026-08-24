"""Standalone consumer for `intake.jobs` (ADR-0027): its own compose service,
not a thread inside the API process, so a container restart mid-file no
longer strands the job the way BackgroundTasks did.

Redelivery is what makes this safe to kill at any point: nothing here is
acked until ProcessIntakeJobUseCase.execute returns, and reprocessing only
ever reads PENDING records back (0.2, 0.3) — the pieces this worker relies on
rather than reimplements."""

import json
import logging
from uuid import UUID

import pika

from domain.exceptions import DomainException
from infrastructure.adapters.input.api.dependencies import (
    get_ingest_lead_use_case,
    get_process_intake_job_use_case,
)
from infrastructure.adapters.output.queue.rabbitmq_job_queue import QUEUE_NAME, declare_intake_topology
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from infrastructure.logging_config import configure_logging

_LOGGER = logging.getLogger(__name__)


def _handle_message(container: Container, channel, method, body: bytes) -> None:
    message = json.loads(body)
    job_id = UUID(message["job_id"])

    # A fresh unit of work per message, same reasoning as one per HTTP
    # request (dependencies.get_uow): it owns a transaction that must not
    # bleed into the next job. Reuses the API's own wiring instead of
    # rebuilding it, so the two call sites cannot drift apart.
    uow = container.unit_of_work()
    ingest = get_ingest_lead_use_case(uow=uow, container=container)
    process_job = get_process_intake_job_use_case(uow=uow, ingest=ingest)

    try:
        process_job.execute(UUID(message["tenant_id"]), job_id)
    except DomainException:
        # Retrying a job that does not exist will never make it exist.
        pass
    except Exception:
        _LOGGER.error("Failed processing intake job %s, requeueing", job_id, exc_info=True)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    configure_logging()
    settings = Settings.from_environment()
    container = Container(settings)

    # ponytail: one connection attempt, no reconnect loop — compose's
    # `restart: on-failure` recovers a dropped broker the same way it
    # recovers a crash. Add backoff-and-retry here if that proves too coarse.
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
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


if __name__ == "__main__":
    main()
